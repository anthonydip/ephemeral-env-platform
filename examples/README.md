# Example Configurations

This directory contains example `.ephemeral-config.yaml` files demonstrating different deployment patterns.

## Examples Overview

| Example                                      | Use Case                   | Services                         |
| -------------------------------------------- | -------------------------- | -------------------------------- |
| [simple-frontend.yaml](#simple-frontend)     | Single service deployment  | Static site or SPA               |
| [fullstack-app.yaml](#fullstack-application) | Complete application stack | Frontend + Backend + Database    |
| [api-only.yaml](#api-service)                | Backend API service        | REST API with environment config |
| [microservices.yaml](#microservices)         | Multi-service architecture | Multiple interconnected services |

---

## Simple Frontend

**File:** `simple-frontend.yaml`

Basic single-service deployment for a static site or React/Vue/Angular application.

```yaml
services:
  - name: frontend
    image: mycompany/frontend:{{PR_NUMBER}}
    port: 80
    ingress:
      enabled: true
      path: "/"
```

**Access:** `http://your-host/pr-123/`

**Use when:**

- Deploying static sites
- Single-page applications without backend
- Preview for UI-only changes

---

## Fullstack Application

**File:** `fullstack-app.yaml`

Complete application stack with frontend, backend API, and database.

```yaml
services:
  - name: frontend
    image: mycompany/frontend:{{PR_NUMBER}}
    port: 3000
    ingress:
      enabled: true
      path: "/"
    env:
      REACT_APP_API_URL: http://your-host/pr-{{PR_NUMBER}}/api

  - name: backend
    image: mycompany/backend:{{PR_NUMBER}}
    port: 5000
    ingress:
      enabled: true
      path: "/api"
    env:
      DATABASE_URL: postgresql://postgres:password@database:5432/myapp
      NODE_ENV: production
      PORT: "5000"

  - name: database
    image: postgres:15-alpine
    port: 5432
    ingress:
      enabled: false
    env:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
```

**Access:**

- Frontend: `http://your-host/pr-123/`
- Backend API: `http://your-host/pr-123/api`
- Database: Internal only (no ingress)

**Use when:**

- Full-stack applications
- Testing frontend and backend changes together
- Database migrations or schema changes

---

## API Service

**File:** `api-only.yaml`

Backend API service with environment configuration.

```yaml
services:
  - name: api
    image: mycompany/api:{{PR_NUMBER}}
    port: 8080
    ingress:
      enabled: true
      path: "/"
    env:
      DATABASE_URL: postgresql://db.example.com:5432/production
      REDIS_URL: redis://cache.example.com:6379
      API_KEY: your-api-key-here
      LOG_LEVEL: info
      CORS_ORIGIN: "*"
```

**Access:** `http://your-host/pr-123/`

**Use when:**

- API-only services
- Testing backend changes
- Integration with external services

---

## Microservices

**File:** `microservices.yaml`

Multiple services communicating with each other.

```yaml
services:
  - name: frontend
    image: mycompany/frontend:{{PR_NUMBER}}
    port: 80
    ingress:
      enabled: true
      path: "/"

  - name: auth-service
    image: mycompany/auth:{{PR_NUMBER}}
    port: 3001
    ingress:
      enabled: true
      path: "/auth"
    env:
      JWT_SECRET: your-secret-key
      TOKEN_EXPIRY: "3600"

  - name: user-service
    image: mycompany/users:{{PR_NUMBER}}
    port: 3002
    ingress:
      enabled: true
      path: "/users"
    env:
      DATABASE_URL: postgresql://postgres:password@user-db:5432/users

  - name: order-service
    image: mycompany/orders:{{PR_NUMBER}}
    port: 3003
    ingress:
      enabled: true
      path: "/orders"
    env:
      DATABASE_URL: postgresql://postgres:password@order-db:5432/orders
      PAYMENT_API_URL: http://payment-service:3004

  - name: payment-service
    image: mycompany/payments:{{PR_NUMBER}}
    port: 3004
    ingress:
      enabled: false
    env:
      STRIPE_KEY: sk_test_example
```

**Access:**

- Frontend: `http://your-host/pr-123/`
- Auth API: `http://your-host/pr-123/auth`
- User API: `http://your-host/pr-123/users`
- Order API: `http://your-host/pr-123/orders`
- Payment service: Internal only

**Use when:**

- Microservices architecture
- Multiple teams working on different services
- Testing service interactions

---

## Template Variables

All examples use `{{PR_NUMBER}}` as a template variable that gets replaced by the GitHub Action:

```yaml
image: mycompany/frontend:{{PR_NUMBER}} # Becomes: mycompany/frontend:123
```

You can also use it in environment variables:

```yaml
env:
  API_URL: http://your-host/pr-{{PR_NUMBER}}/api
```

## Configuration Reference

### Service Schema

```yaml
services:
  - name: string # Service name (required)
    image: string # Docker image (required)
    port: integer # Container port (required)
    ingress: # Ingress configuration (optional)
      enabled: boolean # Enable external access
      path: string # URL path (default: "/")
    env: # Environment variables (optional)
      KEY: value # Key-value pairs
```

### Ingress Paths

Services are accessible via path-based routing:

- `path: "/"` → `http://your-host/pr-123/`
- `path: "/api"` → `http://your-host/pr-123/api`
- `path: "/admin"` → `http://your-host/pr-123/admin`

### Environment Variables

Environment variables can reference:

- External services: `DATABASE_URL: postgresql://external-db:5432/myapp`
- Internal services: `API_URL: http://backend:5000` (uses Kubernetes DNS)
- Template variables: `BASE_URL: http://host/pr-{{PR_NUMBER}}/`
