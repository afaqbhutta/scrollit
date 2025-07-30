from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import urllib
import os
from datetime import timedelta
from azure.storage.blob import BlobServiceClient
from werkzeug.utils import secure_filename
from uuid import uuid4
#from dotenv import load_dotenv
from flask_migrate import Migrate
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import IntegrityError

# to fethc the secret keys from the .env
# load_dotenv()


# Azure Blob Storage settings
AZURE_CONNECTION_STRING = os.environ['AZURE_BLOB_CONN_STRING']
AZURE_CONTAINER_NAME = 'videos'
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

app = Flask(__name__)

# secret key management
app.secret_key = os.environ['SECRET_KEY']

# Session config
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
Session(app)

# Azure SQL connection
server = 'scrollitdb.database.windows.net'
database = 'scrollitDB'
username = 'sohaibadmin'
password = os.environ['SQL_DB_PASSWORD']
driver = '{ODBC Driver 18 for SQL Server}'

# Add timeout parameters
params = urllib.parse.quote_plus(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};'
    f'Connection Timeout=30;Command Timeout=30;Encrypt=yes;TrustServerCertificate=no;'
)
app.config['SQLALCHEMY_DATABASE_URI'] = f'mssql+pyodbc:///?odbc_connect={params}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

migrate = Migrate(app, db)

# To create migration for new Notification model:
# flask db init (only once)
# flask db migrate -m "Add Notification model"
# flask db upgrade

# *** Models for the database entries ***
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    IsCreator = db.Column(db.Boolean, default=False, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    publisher = db.Column(db.String(255), nullable=True)
    producer = db.Column(db.String(255), nullable=True)
    genre = db.Column(db.String(100), nullable=True)
    age_rating = db.Column(db.String(10), nullable=True)  # e.g., PG, 18, etc.
    description = db.Column(db.Text, nullable=True)
    blob_url = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Video {self.title}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    #for the username that commented...
    user = db.relationship('User', backref='comments')

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) 
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_like'),)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# Add view_count to Video if not present
if not hasattr(Video, 'view_count'):
    from sqlalchemy import Integer
    view_count_col = db.Column('view_count', db.Integer, default=0)
    setattr(Video, 'view_count', view_count_col)

# Helper to create a notification
from functools import wraps

def create_notification(user_id, message):
    notif = Notification(user_id=user_id, message=message)
    db.session.add(notif)
    db.session.commit()

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        try:
            user = User.query.get(session['user_id'])
            if user:
                return redirect('/dashboard')
            else:
                session.clear()
                return redirect('/login')
        except Exception as e:
            print(f"Database error: {e}")
            session.clear()
            return redirect('/login')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    print(f"Request method: {request.method}")  # Debug
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        user_types = request.form.getlist('userType')  # Get list of selected checkboxes

        # Validation
        if not username or not email or not password or not confirm_password or not user_types:
            flash("All fields are required", "error")
            return render_template('register.html')

        # Email validation (basic)
        if '@' not in email or '.' not in email:
            flash("Please enter a valid email address", "error")
            return render_template('register.html')

        if not user_types or len(user_types) != 1:
            flash("Please select exactly one user type", "error")
            return render_template('register.html')

        user_type = user_types[0]  # Get the selected user type
        if user_type not in ['creator', 'consumer']:
            flash("Please select a valid user type", "error")
            return render_template('register.html')

        try:
            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash("Username already taken", "error")
                return render_template('register.html')

            # To check if email already exists
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash("Email already registered", "error")
                return render_template('register.html')

            # Convert user_type to bit (0 for consumer, 1 for creator)
            is_creator = 1 if user_type == 'creator' else 0

            # Store hashed password
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username, 
                email=email, 
                password=hashed_password,
                IsCreator=is_creator  # Assuming your User model has is_creator field
            )
            db.session.add(new_user)
            db.session.commit()

            flash("Registration successful! Please login.", "success")
            return redirect('/login')
        # in case the database is not connected or is not working
        except Exception as e:
            db.session.rollback()
            print(f"Database error: {e}")
            flash("Registration failed. Please try again.", "error")
            return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.clear()
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Please enter both username and password", "error")
            return render_template('login.html')

        try:
            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['email'] = user.email
                session['IsCreator'] = user.IsCreator  # Store user type in session
                
                flash(f"Welcome back, {user.username}!", "success")
                
                # Route based on user type
                if user.IsCreator == 1:  # Creator
                    return redirect('/creator')
                else:  # Consumer
                    return redirect('/consumer')
            else:
                flash("Invalid username or password", "error")
                return render_template('login.html')
        
        #exception for the database connection
        except Exception as e:
            print(f"Database error: {e}")
            flash("Login failed. Please try again.", "error")
            return render_template('login.html')

    return render_template('login.html')

@app.route('/creator', methods=['GET', 'POST'])
def creator():
    if 'user_id' not in session or session.get('IsCreator') != 1:
        flash("Access denied. Creator account required.", "error")
        return redirect('/login')
    try:
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            publisher = request.form.get('publisher')
            producer = request.form.get('producer')
            genre = request.form.get('genre')
            age_rating = request.form.get('age_rating')
            file = request.files.get('video')
            if not file or not title:
                flash("Title and video file are required.", "error")
                return redirect('/creator')
            try:
                filename = secure_filename(file.filename)
                unique_name = f"{uuid4()}_{filename}"
                blob_client = blob_container_client.get_blob_client(unique_name)
                blob_client.upload_blob(file.stream, overwrite=True)
                blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{unique_name}"
                video = Video(
                    title=title,
                    description=description,
                    publisher=publisher,
                    producer=producer,
                    genre=genre,
                    age_rating=age_rating,
                    blob_url=blob_url,
                    uploaded_by=session['user_id']
                )
                db.session.add(video)
                db.session.commit()
                flash("Video uploaded successfully!", "success")
            except Exception as e:
                print(f"Upload error: {e}")
                db.session.rollback()
                flash("Video upload failed.", "error")
            return redirect('/creator')  # Redirect after POST
        # GET: Render creator upload page
        return render_template('creator.html')
    except OperationalError as e:
        print(f"SQL connection error: {e}")
        session.clear()
        flash("Database connection error. Please log in again.", "error")
        return redirect('/login')
    except Exception as e:
        print(f"Creator error: {e}")
        session.clear()
        flash("Unexpected error. Please log in again.", "error")
        return redirect('/login')


#route for the videos uploaded by the creator
@app.route('/creator/videos', methods=['GET', 'POST'])
def creator_videos():
    if 'user_id' not in session or session.get('IsCreator') != 1:
        flash("Access denied. Creator account required.", "error")
        return redirect('/login')

    if request.method == 'POST' and 'delete_video_id' in request.form:
        video_id = int(request.form.get('delete_video_id'))
        video = Video.query.filter_by(id=video_id, uploaded_by=session['user_id']).first()
        if not video:
            flash("Video not found or unauthorized.", "error")
            return redirect('/creator/videos')
        try:
            blob_name = video.blob_url.split('/')[-1]
            blob_client = blob_container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            db.session.delete(video)
            db.session.commit()
            flash("Video deleted successfully!", "success")
        except Exception as e:
            print(f"Deletion error: {e}")
            db.session.rollback()
            flash("Failed to delete video.", "error")
        return redirect('/creator/videos')

    videos = Video.query.filter_by(uploaded_by=session['user_id']).order_by(Video.uploaded_at.desc()).all()
    return render_template('creatorVideos.html', videos=videos)


# Route for consumer dashboard
@app.route('/consumer', methods = ['GET', 'POST'])
def consumer():
    # Check if user is logged in
    if 'user_id' not in session:
        flash("Please log in first", "error")
        return redirect('/login')
    
    return redirect('/dashboard')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to view the dashboard", "error")
        return redirect('/login')
    try:
        # Handle POST: comment, rating or comment deletion
        if request.method == 'POST':
            try:
                # Delete comment
                delete_comment_id = request.form.get('delete_comment_id')
                if delete_comment_id:
                    comment = Comment.query.get(int(delete_comment_id))
                    if comment and comment.user_id == session['user_id']:
                        db.session.delete(comment)
                        db.session.commit()
                        flash("Comment deleted", "info")
                    else:
                        flash("Unauthorized or comment not found", "error")
                    return redirect('/dashboard')

                # Submit comment and/or rating
                video_id = request.form.get('video_id')
                comment_text = request.form.get('comment')
                rating_value = request.form.get('rating')

                if comment_text:
                    comment = Comment(
                        video_id=video_id,
                        user_id=session['user_id'],
                        content=comment_text
                    )
                    db.session.add(comment)
                    # Notify video owner
                    video = Video.query.get(video_id)
                    if video and video.uploaded_by != session['user_id']:
                        create_notification(video.uploaded_by, f"{session['username']} commented on your video '{video.title}'")

                if rating_value:
                    existing_rating = Rating.query.filter_by(video_id=video_id, user_id=session['user_id']).first()
                    if existing_rating:
                        existing_rating.rating = int(rating_value)
                    else:
                        rating = Rating(
                            video_id=video_id,
                            user_id=session['user_id'],
                            rating=int(rating_value)
                        )
                        db.session.add(rating)
                    # Notify video owner
                    video = Video.query.get(video_id)
                    if video and video.uploaded_by != session['user_id']:
                        create_notification(video.uploaded_by, f"{session['username']} rated your video '{video.title}'")

                db.session.commit()
                flash("Feedback submitted!", "success")

            except Exception as e:
                db.session.rollback()
                print(f"Error: {e}")
                flash("Something went wrong", "error")

            return redirect('/dashboard')

        # GET: Search and display videos
        search_query = request.args.get('search', '').strip()
        if search_query:
            videos = Video.query.filter(
                (Video.title.ilike(f'%{search_query}%')) |
                (Video.description.ilike(f'%{search_query}%'))
            ).order_by(Video.uploaded_at.desc()).all()
        else:
            videos = Video.query.order_by(Video.uploaded_at.desc()).all()

        # Prepare video data
        video_data = []
        for video in videos:
            comments = Comment.query.filter_by(video_id=video.id).order_by(Comment.created_at.desc()).all()
            # Load usernames with comments
            for comment in comments:
                comment.user = User.query.get(comment.user_id)

            ratings = Rating.query.filter_by(video_id=video.id).all()
            avg_rating = round(sum(r.rating for r in ratings) / len(ratings), 2) if ratings else None
            user_rating = None
            if 'user_id' in session:
                user_rating_obj = Rating.query.filter_by(video_id=video.id, user_id=session['user_id']).first()
                user_rating = user_rating_obj.rating if user_rating_obj else None
            # Add like info
            user_liked = False
            if 'user_id' in session:
                user_liked = Like.query.filter_by(video_id=video.id, user_id=session['user_id']).first() is not None
            total_likes = Like.query.filter_by(video_id=video.id).count()
            video_data.append({
                "video": video,
                "comments": comments,
                "avg_rating": avg_rating,
                "user_rating": user_rating,
                "user_liked": user_liked,
                "total_likes": total_likes
            })

        return render_template('dashboard.html', video_data=video_data)
    except OperationalError as e:
        print(f"SQL connection error: {e}")
        session.clear()
        flash("Database connection error. Please log in again.", "error")
        return redirect('/login')
    except Exception as e:
        print(f"Dashboard error: {e}")
        session.clear()
        flash("Unexpected error. Please log in again.", "error")
        return redirect('/login')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash("Please log in to view your profile", "error")
        return redirect('/login')
    try:
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash("User not found. Please log in again.", "error")
            return redirect('/login')

        # My Videos with stats
        user_videos = Video.query.filter_by(uploaded_by=user.id).order_by(Video.uploaded_at.desc()).all()
        user_videos_stats = []
        for video in user_videos:
            likes = Like.query.filter_by(video_id=video.id).count()
            comments = Comment.query.filter_by(video_id=video.id).count()
            views = getattr(video, 'view_count', 0)
            user_videos_stats.append({
                'video': video,
                'likes': likes,
                'comments': comments,
                'views': views
            })
        # Liked Videos with stats
        liked_videos = []
        liked_videos_stats = []
        if hasattr(user, 'liked_videos'):
            liked_videos = user.liked_videos
        elif hasattr(Video, 'likes'):
            liked_videos = Video.query.join(Like, Like.video_id == Video.id).filter(Like.user_id == user.id).all()
        for video in liked_videos:
            likes = Like.query.filter_by(video_id=video.id).count()
            comments = Comment.query.filter_by(video_id=video.id).count()
            views = getattr(video, 'view_count', 0)
            liked_videos_stats.append({
                'video': video,
                'likes': likes,
                'comments': comments,
                'views': views
            })
        return render_template('profile.html', user=user, user_videos=user_videos_stats, liked_videos=liked_videos_stats)
    except OperationalError as e:
        print(f"SQL connection error: {e}")
        session.clear()
        flash("Database connection error. Please log in again.", "error")
        return redirect('/login')
    except Exception as e:
        print(f"Profile error: {e}")
        session.clear()
        flash("Unexpected error. Please log in again.", "error")
        return redirect('/login')

#logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully", "info")
    return redirect('/')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return "Internal server error", 500

@app.route('/notifications')
def get_notifications():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    notifs = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
    return {'success': True, 'notifications': [
        {'id': n.id, 'message': n.message, 'is_read': n.is_read, 'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')} for n in notifs
    ]}

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    notif_id = request.form.get('notif_id')
    notif = Notification.query.get(notif_id)
    if not notif or notif.user_id != session['user_id']:
        return {'success': False, 'error': 'Unauthorized or not found'}, 403
    notif.is_read = True
    db.session.commit()
    return {'success': True}

# Add notification creation to like, comment, rating, video actions
# Like notification (notify video owner if not self)
@app.route('/like', methods=['POST'])
def like_video():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    video_id = request.form.get('video_id')
    if not video_id:
        return {'success': False, 'error': 'No video id'}, 400
    video = Video.query.get(video_id)
    if not video:
        return {'success': False, 'error': 'Video not found'}, 404
    try:
        like = Like.query.filter_by(user_id=session['user_id'], video_id=video_id).first()
        if like:
            db.session.delete(like)
            db.session.commit()
            liked = False
        else:
            new_like = Like(user_id=session['user_id'], video_id=video_id)
            db.session.add(new_like)
            db.session.commit()
            liked = True
            if video.uploaded_by != session['user_id']:
                create_notification(video.uploaded_by, f"{session['username']} liked your video '{video.title}'")
        total_likes = Like.query.filter_by(video_id=video_id).count()
        return {'success': True, 'liked': liked, 'total_likes': total_likes}
    except IntegrityError:
        db.session.rollback()
        # If duplicate like, treat as already liked
        total_likes = Like.query.filter_by(video_id=video_id).count()
        return {'success': True, 'liked': True, 'total_likes': total_likes}
    except Exception as e:
        db.session.rollback()
        print(f"Like error: {e}")
        return {'success': False, 'error': str(e)}, 500

# Increment view count
@app.route('/view', methods=['POST'])
def view_video():
    video_id = request.form.get('video_id')
    video = Video.query.get(video_id)
    if not video:
        return {'success': False, 'error': 'Video not found'}, 404
    try:
        video.view_count = (video.view_count or 0) + 1
        db.session.commit()
        return {'success': True, 'view_count': video.view_count}
    except Exception as e:
        db.session.rollback()
        print(f"View error: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/edit_comment', methods=['POST'])
def edit_comment():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    comment_id = request.form.get('comment_id')
    new_content = request.form.get('content')
    comment = Comment.query.get(comment_id)
    if not comment or comment.user_id != session['user_id']:
        return {'success': False, 'error': 'Unauthorized or comment not found'}, 403
    comment.content = new_content
    db.session.commit()
    return {'success': True, 'content': new_content}

@app.route('/delete_comment', methods=['POST'])
def delete_comment():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    comment_id = request.form.get('comment_id')
    comment = Comment.query.get(comment_id)
    if not comment or comment.user_id != session['user_id']:
        return {'success': False, 'error': 'Unauthorized or comment not found'}, 403
    db.session.delete(comment)
    db.session.commit()
    return {'success': True}

@app.route('/rate', methods=['POST'])
def rate_video():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    video_id = request.form.get('video_id')
    rating_value = request.form.get('rating')
    if not video_id or not rating_value:
        return {'success': False, 'error': 'Missing data'}, 400
    try:
        rating_value = int(rating_value)
        if rating_value < 1 or rating_value > 5:
            raise ValueError
    except Exception:
        return {'success': False, 'error': 'Invalid rating'}, 400
    rating = Rating.query.filter_by(video_id=video_id, user_id=session['user_id']).first()
    if rating:
        rating.rating = rating_value
    else:
        rating = Rating(video_id=video_id, user_id=session['user_id'], rating=rating_value)
        db.session.add(rating)
    db.session.commit()
    # Calculate new average
    ratings = Rating.query.filter_by(video_id=video_id).all()
    avg_rating = round(sum(r.rating for r in ratings) / len(ratings), 2) if ratings else None
    return {'success': True, 'avg_rating': avg_rating, 'user_rating': rating_value}

@app.route('/delete_video', methods=['POST'])
def delete_video():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    video_id = request.form.get('video_id')
    video = Video.query.get(video_id)
    if not video or video.uploaded_by != session['user_id']:
        return {'success': False, 'error': 'Unauthorized or video not found'}, 403
    try:
        blob_name = video.blob_url.split('/')[-1]
        blob_client = blob_service_client.get_blob_client(blob_name)
        blob_client.delete_blob()
        db.session.delete(video)
        db.session.commit()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    try:
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return {'success': False, 'error': 'User not found'}, 404
        username = request.form.get('username')
        email = request.form.get('email')
        bio = request.form.get('bio')
        avatar_file = request.files.get('avatar')
        if username:
            user.username = username
            session['username'] = username
        if email:
            user.email = email
            session['email'] = email
        if bio is not None:
            user.bio = bio
        if avatar_file and avatar_file.filename:
            filename = secure_filename(avatar_file.filename)
            unique_name = f"avatars/{uuid4()}_{filename}"
            avatar_blob_client = blob_service_client.get_blob_client(unique_name)
            avatar_blob_client.upload_blob(avatar_file.stream, overwrite=True)
            avatar_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{unique_name}"
            user.avatar_url = avatar_url
            session['avatar_url'] = avatar_url
        db.session.commit()
        return {'success': True, 'username': user.username, 'email': user.email, 'bio': user.bio, 'avatar_url': getattr(user, 'avatar_url', None)}
    except OperationalError as e:
        print(f"SQL connection error: {e}")
        session.clear()
        return {'success': False, 'error': 'Database connection error. Please log in again.'}, 500
    except Exception as e:
        db.session.rollback()
        print(f"Edit profile error: {e}")
        return {'success': False, 'error': str(e)}, 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)