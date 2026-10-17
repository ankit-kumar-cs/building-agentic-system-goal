# Design Document

Feature: Design the database schema for product reviews

Date: 2026-10-17

Client: Acme | Project: Customer Portal

## Description:

Design the database schema for product reviews

## Design Outline:

- **Components**
  - Review Service
    - Handles business logic for creating, updating, deleting, and retrieving reviews.
  - Review API
    - Exposes endpoints for client applications and third‑party integrations.
  - Review UI
    - Front‑end components for submitting and displaying reviews.
  - Review Analytics
    - Aggregates review data for reporting and recommendation engines.
- **Data**
  - **Tables**
    - `products` (id, name, sku, etc.)
    - `users` (id, name, email, etc.)
    - `reviews` (id, product_id, user_id, rating, title, body, created_at, updated_at, status)
    - `review_images` (id, review_id, url, alt_text, created_at)
    - `review_tags` (id, review_id, tag)
    - `review_likes` (id, review_id, user_id, created_at)
  - **Indexes**
    - Composite index on (`product_id`, `created_at`) for fast product review listing.
    - Full‑text index on `title` and `body` for search.
  - **Constraints**
    - Foreign keys: `reviews.product_id → products.id`, `reviews.user_id → users.id`.
    - Unique constraint on (`review_id`, `user_id`) to prevent duplicate reviews.
- **Interfaces**
  - **REST API**
    - `POST /products/{productId}/reviews` – create review
    - `GET /products/{productId}/reviews` – list reviews
    - `GET /reviews/{reviewId}` – get review details
    - `PUT /reviews/{reviewId}` – update review
    - `DELETE /reviews/{reviewId}` – delete review
  - **GraphQL**
    - Query `productReviews(productId: ID!, first: Int, after: String)` for paginated reviews.
    - Mutation `submitReview(input: ReviewInput!)` for creating reviews.
  - **Webhooks**
    - `review.created`, `review.updated`, `review.deleted` events for downstream services.
  - **Admin UI**
    - Review moderation panel with status change, flagging, and bulk actions.
  - **Integration Points**
    - Recommendation engine consumes `reviews` and `review_ratings` for personalized suggestions.
    - Search service indexes `reviews` for full‑text search.

## Next Steps:

- Review design with the team
- Move to implementation phase
