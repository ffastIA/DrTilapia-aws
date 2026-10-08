## MODIFIED Requirements

### Requirement: The landing page and auth screens share one visual identity
Every route in the application SHALL use the same design tokens (typography, color palette, spacing, border radius) derived from the "Dr. Tilap-IA" design reference — not just the landing page and the login/forgot-password screens. The tokens SHALL be defined in a single source (`frontend/lib/tokens.ts`) consumed by both the Tailwind configuration and the landing's CSS Module, so there is exactly one place to change a color or font.

#### Scenario: Login and forgot-password share the landing's design tokens
- **WHEN** `/auth/login` or `/auth/forgot-password` is rendered
- **THEN** it uses the same font families, color tokens, and component styling (buttons, form fields, cards) as the home page

#### Scenario: All application routes share the landing's design tokens
- **WHEN** any route under `/main/*` or `/auth/signup`, `/auth/callback` is rendered
- **THEN** it uses the same font families (Barlow / Barlow Condensed), color tokens (background, surface, foreground, primary, border, destructive, success), and square-cornered, shadow-free component styling as the home page — not the previous dark green/purple theme

#### Scenario: A single design-token source drives the whole app
- **WHEN** a color or font value is changed in `frontend/lib/tokens.ts`
- **THEN** the change propagates to both the Tailwind-driven pages and the landing's CSS Module without any other file needing an update to the same literal value

## ADDED Requirements

### Requirement: Visual restyling of non-auth routes preserves existing functional behavior
Restyling any route under `/main/*` (hub, consultoria, dashboard, admin, videos, images, images/dashboard, profile) SHALL NOT change any API call, data-fetching hook, mutation, route, or business logic — only presentation.

#### Scenario: RAG chat behavior is unchanged after restyling
- **WHEN** a user sends a message, receives a response with sources, or clears the chat on the restyled `/main/consultoria` screen
- **THEN** the same requests, responses, and source citations occur as before the restyle

#### Scenario: Admin document management behavior is unchanged after restyling
- **WHEN** an admin uploads a PDF, deletes a document, or purges the knowledge base on the restyled `/main/admin` screen
- **THEN** the same requests and confirmation flows occur as before the restyle

#### Scenario: Image biometry and video library behavior is unchanged after restyling
- **WHEN** a user uploads fish images for biometry on `/main/images`, views a biometric dashboard on `/main/images/dashboard`, or plays/uploads a video on `/main/videos`
- **THEN** the same calculations, chart data, and playback/upload behavior occur as before the restyle

### Requirement: Shared navigation shell for authenticated routes
All routes under `/main/*` SHALL use a single shared layout for their page frame and back-navigation control, instead of each page re-implementing its own header and back button.

#### Scenario: Back navigation is consistent across authenticated routes
- **WHEN** a user is on any `/main/*` page and uses the back control
- **THEN** it renders with the same visual style everywhere and follows the same navigation rule (return to the previous page in history, or `/main/hub` if there is no previous page)
