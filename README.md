# BuilderHub-API

A production-style website builder backend built with Django and Django REST Framework. It supports user authentication, site management, page management, Swagger-based API documentation, and Ruff-based code quality checks.

## Tech Stack

- Backend: Django + Django REST Framework
- Authentication: JWT with djangorestframework-simplejwt
- API documentation: drf-spectacular (Swagger UI, Redoc, OpenAPI schema)
- Code quality: Ruff for linting and formatting
- Database: PostgreSQL (via Docker Compose)
- Environment config: python-dotenv

## Project Structure

```text
BuilderHub-API/
├── apps/
│   ├── core/              # Auth, health checks, shared helpers
│   ├── sites/             # Site models, serializers, views, URLs
│   └── pages/             # Page models, serializers, views, URLs
├── config/                # Django settings and URL routing
├── media/                 # Uploaded files in development
├── schema.yml             # Generated OpenAPI schema
├── docker-compose.yml     # PostgreSQL container setup
├── manage.py
├── pyproject.toml         # Ruff configuration
├── requirements.txt
└── README.md
```

## Prerequisites

Before setting up the project, make sure you have:

- Python 3.10+
- Docker Desktop or Docker Engine with Docker Compose
- A virtual environment tool such as `venv`
- Internet access to install dependencies

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Shahriar-Hasan123/BuilderHub-API.git
cd BuilderHub-API
```

### 2. Create and activate a virtual environment

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

> Note: `DB_HOST=localhost` is used because the database runs in Docker while Django runs locally.

### 5. Start PostgreSQL with Docker

```bash
docker compose up -d
docker compose ps
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

The API will be available at http://127.0.0.1:8000/.

## Environment Variables Reference

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Debug mode (`True`/`False`) |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |

## API Endpoints

All API routes are versioned under `/api/v1/`.

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health/` | Checks API and database connectivity |

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/auth/register/` | Register a new user | No |
| POST | `/api/v1/auth/login/` | Obtain JWT access and refresh tokens | No |
| POST | `/api/v1/auth/refresh/` | Refresh JWT access token | No |

### Sites

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/sites/` | List sites owned by the current user | Yes |
| POST | `/api/v1/sites/` | Create a new site | Yes |
| GET | `/api/v1/sites/{id}/` | Retrieve a specific site | Yes |
| PUT | `/api/v1/sites/{id}/` | Replace a site | Yes |
| PATCH | `/api/v1/sites/{id}/` | Partially update a site | Yes |
| DELETE | `/api/v1/sites/{id}/` | Delete a site | Yes |

### Pages

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/sites/{site_pk}/pages/` | List pages for a specific site | Yes |
| POST | `/api/v1/sites/{site_pk}/pages/` | Create a page under a site | Yes |
| GET | `/api/v1/sites/{site_pk}/pages/{id}/` | Retrieve a specific page | Yes |
| PUT | `/api/v1/sites/{site_pk}/pages/{id}/` | Replace a page | Yes |
| PATCH | `/api/v1/sites/{site_pk}/pages/{id}/` | Partially update a page | Yes |
| DELETE | `/api/v1/sites/{site_pk}/pages/{id}/` | Delete a page | Yes |

## Authentication Flow

1. Register a user via `/api/v1/auth/register/`
2. Obtain tokens via `/api/v1/auth/login/` with `username` and `password`
3. Include the access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

4. Refresh the access token via `/api/auth/refresh/` when it expires

## Swagger / OpenAPI

This project uses `drf-spectacular` for API documentation.

### Generate schema

```bash
python manage.py spectacular --format openapi > schema.yml
```

### Validate schema

```bash
python manage.py spectacular --validate
```

### Open the docs

- Swagger UI: http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Redoc: http://127.0.0.1:8000/api/redoc/

## Code Quality

This project uses Ruff for linting and formatting.

```bash
ruff check .
ruff format .
```

## Development Notes

- Refresh tokens rotate and are blacklisted after rotation to prevent replay attacks.
- Site ownership is enforced so users can manage only their own sites and pages.
- Media files are served locally in development; production should use cloud storage such as S3.

## Git Workflow

This project follows a feature-branch workflow with concise commit messages.

```bash
git checkout -b feature/<short-description>
```

Example commit message:

```text
Add Ruff formatter and Swagger docs support
```

## License

Add your preferred license information here.
