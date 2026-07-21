# BuilderHub-API

A production-style website builder backend built with Django and Django REST Framework. It supports user authentication, site management, page management, Swagger-based API documentation, Redis-backed caching, and Ruff-based code quality checks.

## Tech Stack

- Backend: Django + Django REST Framework
- Authentication: JWT with djangorestframework-simplejwt
- API documentation: drf-spectacular (Swagger UI, Redoc, OpenAPI schema)
- Code quality: Ruff for linting and formatting
- Database: PostgreSQL (via Docker Compose)
- Cache and distributed locks: Redis
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

REDIS_HOST=localhost
REDIS_PORT=6379
TTL_SECONDS=300
```

> Note: `DB_HOST=localhost` is used because the database runs in Docker while Django runs locally. Redis is also expected to be available on `localhost:6379` for development.

### 5. Start PostgreSQL and Redis with Docker

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
| `REDIS_HOST` | Redis host for cache and distributed locks |
| `REDIS_PORT` | Redis port |
| `TTL_SECONDS` | Time-to-live for Redis-based site locks in seconds |

## Redis Cache and Site Locking

This project uses Redis for two purposes:

- Django cache backend via `django-redis`
- Distributed site edit locks to prevent concurrent editing of the same site

### How Site Locks Work

The lock system uses a Redis key per site that expires after the configured `RESOURCE_LOCK_TTL_SECONDS` value (default: 300 seconds). A lock is automatically acquired when a user:

- Creates a page under a site
- Updates (PUT/PATCH) a page in a site
- Updates (PUT/PATCH) a site itself
- Deletes a page or site

### Lock Lifecycle

1. **Acquire** (`POST /api/v1/sites/{id}/lock/`): User acquires an exclusive lock
   - Returns `201 Created` with lock status if successful
   - Returns `409 Conflict` if another user already holds the lock

2. **Check Status** (`GET /api/v1/sites/{id}/lock/`): Check who (if anyone) holds the lock
   - Returns lock details: `user_id`, `locked_by`, `locked_at`, `ttl_remaining_seconds`

3. **Refresh** (`PATCH /api/v1/sites/{id}/lock/`): Extend lock expiration (must hold the lock)
   - Useful for long-running operations to keep the lock alive
   - Returns `200 OK` with updated TTL

4. **Release** (`DELETE /api/v1/sites/{id}/lock/`): Voluntarily release the lock
   - Returns `204 No Content`

### Lock Enforcement

Edit operations (page/site creation, update, delete) automatically enforce locks via the `SiteLockMixin`:

- If the site is already locked by another user, the operation returns `409 Conflict`
- The current user's lock is automatically refreshed on each operation
- Locks expire automatically if the user becomes inactive

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
| GET | `/api/v1/sites/{pk}/` | Retrieve a specific site | Yes |
| PUT | `/api/v1/sites/{pk}/` | Replace a site | Yes |
| PATCH | `/api/v1/sites/{pk}/` | Partially update a site | Yes |
| DELETE | `/api/v1/sites/{pk}/` | Delete a site | Yes |

### Site Locks

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/sites/{pk}/lock/` | Get lock status for a site | Yes |
| POST | `/api/v1/sites/{pk}/lock/` | Acquire lock for a site | Yes |
| PATCH | `/api/v1/sites/{pk}/lock/` | Refresh lock expiration | Yes |
| DELETE | `/api/v1/sites/{pk}/lock/` | Release lock for a site | Yes |

### Pages

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/sites/{site_pk}/pages/` | List pages for a specific site | Yes |
| POST | `/api/v1/sites/{site_pk}/pages/` | Create a page under a site | Yes |
| GET | `/api/v1/sites/{site_pk}/pages/{pk}/` | Retrieve a specific page | Yes |
| PUT | `/api/v1/sites/{site_pk}/pages/{pk}/` | Replace a page | Yes |
| PATCH | `/api/v1/sites/{site_pk}/pages/{pk}/` | Partially update a page | Yes |
| DELETE | `/api/v1/sites/{site_pk}/pages/{pk}/` | Delete a page | Yes |

## Google Docs Blog Importer

Batch import blog articles directly from a public Google Docs document. Each tab in the document becomes a separate blog page.

### Features

- Converts Google Docs tabs to blog pages automatically
- Processes embedded images and saves them locally
- Sanitizes HTML to prevent XSS attacks
- Supports batch imports with detailed status reporting
- Idempotent: re-running imports with identical content skips unnecessary updates
- Cleans up old media files on updates

### How to Use

1. **Prepare a public Google Docs document** with blog content in separate tabs
2. **Get the document ID** from the URL: `docs.google.com/document/d/{DOC_ID}/`
3. **Get tab IDs** by inspecting the document (visible in URL parameters)
4. **Run the import command**:

```bash
python manage.py import_blogs \
  --doc-id "YOUR_GOOGLE_DOCS_ID" \
  --tabs "t.0,t.abc123,t.xyz789" \
  --site-id 1
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--doc-id` | Yes | Google Docs document ID |
| `--tabs` | Yes | Comma-separated tab IDs (e.g., `t.0,t.tab1,t.tab2`) |
| `--site-id` | Yes | Target site ID in the database |

### Example Output

```
✓ created  Building a Scalable Django Application for Production
✓ updated  Understanding REST API Design Principles
→ skipped  The Importance of Cloud Computing in Modern Development
✗ failed   Invalid Document  (No <h1> title found in tab)

Done — created: 1, updated: 1, skipped: 1, failed: 1
```

### Processing Pipeline

1. **Fetch**: Exports HTML from each Google Docs tab
2. **Images**: Extracts embedded images and saves locally to `media/pages/images/`
3. **Clean**: Removes unwanted HTML tags and attributes, preserves structure
4. **Sanitize**: Bleach sanitization to prevent XSS
5. **Create/Update**: Stores pages as drafts with BLOG type

### Notes

- Pages are created with `status=DRAFT` automatically
- Each page gets a unique slug based on the H1 title
- Image files are deduplicated by content hash
- Failed tabs don't halt the batch process; results are logged for each tab

## Authentication Flow

1. Register a user via `/api/v1/auth/register/`
2. Obtain tokens via `/api/v1/auth/login/` with `username` and `password`
3. Include the access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

4. Refresh the access token via `/api/v1/auth/refresh/` when it expires

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

- Swagger UI: http://127.0.0.1:8000/api/v1/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/v1/schema/
- Redoc: http://127.0.0.1:8000/api/v1/redoc/

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
