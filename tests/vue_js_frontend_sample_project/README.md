# Vue.js Crypto Dashboard

A dashboard application for tracking cryptocurrency prices and trends, built with Vue.js.

## Features
- Fetches and displays a list of top cryptocurrencies from an external API.
- Provides a detailed view for each cryptocurrency with a historical price chart.
- Uses Vue Router for client-side navigation.
- Manages application state using Pinia.
- Demonstrates a modular component-based architecture.

## Key Architectural Components
- **`main.js`**: Application entry point. Initializes Vue, Router, and Pinia.
- **`router.js`**: Defines the application routes (`/` and `/coin/:id`).
- **`store.js`**: Defines the Pinia store for state management (e.g., fetching and storing crypto data).
- **`services/cryptoApi.js`**: A module abstracting the communication with the external crypto API.
- **`views/`**: Contains top-level components for each route.
- **`components/`**: Contains reusable UI components used across different views.