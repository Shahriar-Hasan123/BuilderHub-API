# BuilderHub-API

A production-level website builder backend (Wix/Webflow-style), built with Django REST Framework. Allows users to create sites, manage pages under each site, and (in future) collaborate with team members on shared sites.

## Tech Stack

- **Backend Framework:** Django + Django REST Framework
- **Database:** PostgreSQL (Dockerized)
- **Authentication:** JWT (djangorestframework-simplejwt)
- **Environment Config:** python-dotenv

## Project Structure

A cleaner, more scalable layout for this project looks like this:

```text
BuilderHub-API/
├── apps/
│   ├── core/              # Shared models, validators, auth helpers, health checks
│   ├── sites/             # Site-related models, serializers, views, URLs
│   └── pages/             # Page-related models, serializers, views, URLs
├── config/                # Django settings, URL routing, ASGI/WSGI entrypoints
├── media/                 # Uploaded files in development
├── docs/                  # API docs and project notes
├── tests/                 # Integration and API tests
├── .env.example           # Sample environment variables
├── .gitignore
├── docker-compose.yml     # PostgreSQL container setup
├── manage.py
├── requirements.txt
└── README.md
```

This keeps domain-specific code grouped by feature while leaving shared infrastructure in a dedicated configuration layer.

## Prerequisites

Before setting up the project, make sure you have:

- Python 3.10+ (or the version used in your local environment)
- Docker Desktop or Docker Engine with Docker Compose
- A virtual environment tool such as `venv` or `virtualenv`
- Internet access to install Python dependencies

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Shahriar-Hasan123/BuilderHub-API.git
cd BuilderHub-API
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

> **Note:** `DB_HOST=localhost` is used because only PostgreSQL runs inside Docker — Django itself runs locally against the containerized database.

### 5. Start PostgreSQL (Docker)

```bash
docker compose up -d
docker compose ps    # confirm the db service is healthy
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create a superuser (optional, for Django admin)

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`.

## Environment Variables Reference

| Variable      | Description                          |
|---------------|---------------------------------------|
| `SECRET_KEY`  | Django secret key                    |
| `DEBUG`       | Debug mode (`True`/`False`)          |
| `DB_NAME`     | PostgreSQL database name             |
| `DB_USER`     | PostgreSQL username                  |
| `DB_PASSWORD` | PostgreSQL password                  |
| `DB_HOST`     | Database host (`localhost` for local Django + Dockerized DB) |
| `DB_PORT`     | Database port (default `5432`)       |

## API Endpoints

### Health Check
| Method | Endpoint          | Description                    |
|--------|-------------------|---------------------------------|
| GET    | `/api/health/`     | Checks API and DB connectivity |

### Authentication
| Method | Endpoint                  | Description                       | Auth Required |
|--------|---------------------------|------------------------------------|---------------|
| POST   | `/api/auth/register/`     | Register a new user               | No            |
| POST   | `/api/auth/login/`        | Obtain JWT access & refresh token  | No            |
| POST   | `/api/auth/refresh/`      | Refresh JWT access token           | No            |

### Sites
| Method | Endpoint            | Description                        | Auth Required |
|--------|----------------------|------------------------------------|---------------|
| GET    | `/api/sites/`         | List sites owned by current user   | Yes           |
| POST   | `/api/sites/`         | Create a new site                  | Yes           |
| GET    | `/api/sites/{id}/`    | Retrieve a specific site           | Yes           |
| PUT/PATCH | `/api/sites/{id}/` | Update a site                      | Yes           |
| DELETE | `/api/sites/{id}/`    | Delete a site                      | Yes           |

### Pages
| Method | Endpoint                                        | Description                                         | Auth Required |
|--------|-------------------------------------------------|-----------------------------------------------------|---------------|
| GET    | `/api/sites/{site_pk}/pages/`                    | List pages for a specific site                      | Yes           |
| POST   | `/api/sites/{site_pk}/pages/`                    | Create a new page under a specific site             | Yes           |
| GET    | `/api/sites/{site_pk}/pages/{id}/`               | Retrieve a specific page                            | Yes           |
| PUT/PATCH | `/api/sites/{site_pk}/pages/{id}/`            | Update a page                                       | Yes           |
| DELETE | `/api/sites/{site_pk}/pages/{id}/`               | Delete a page                                       | Yes           |

## Authentication Flow

1. Register a user via `/api/auth/register/`
2. Obtain tokens via `/api/auth/login/` with `username` and `password`
3. Include the access token in subsequent requests:
```

Authorization: Bearer <access_token>

```
4. Refresh the access token via `/api/auth/refresh/` when it expires

## Development Notes

- Refresh tokens rotate on use and are blacklisted after rotation to prevent replay attacks.
- Site ownership is enforced at the serializer level — users can only create/manage pages under sites they own.
- File uploads (favicon, logo, global CSS, page HTML/CSS) are served locally in development via Django's media handling; a production setup should use cloud storage (e.g. S3) instead.

## Git Workflow

This project follows feature-branch workflow with Conventional Commits:

```bash
git checkout -b feature/<short-description>
```

Commit format:
```

<type>: <short summary>

- <detail 1>
- <detail 2>

```
## License

_Add license information here._
