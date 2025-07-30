# DoomScroll - Social Media App

A Flask-based social media application inspired by Instagram Reels and TikTok. This project provides a platform for users to share and discover short-form video content.

## Features

- User authentication and registration
- Video upload and sharing
- Feed browsing for consumers
- Creator dashboard for content management
- User profiles with bio and avatar support
- Notification system
- Responsive web interface

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy with Alembic migrations
- **Frontend**: HTML, CSS, JavaScript
- **Session Management**: Flask-Session
- **Development**: Docker container support

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repository-url>
   cd socrll-it-main
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=sqlite:///app.db
   ```

5. **Initialize the database**
   ```bash
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:5000`

## Project Structure

```
socrll-it-main/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── migrations/           # Database migrations
├── static/              # CSS, JS, and static assets
├── templates/           # HTML templates
├── .devcontainer/       # Docker development setup
└── README.md           # This file
```

## Usage

1. **Register/Login**: Create an account or log in to access the platform
2. **Consumer Mode**: Browse and watch videos from other creators
3. **Creator Mode**: Upload and manage your own video content
4. **Profile**: Customize your profile with bio and avatar

## Development

This project includes Docker support for development. You can use the `.devcontainer` configuration to run the application in a containerized environment.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).
