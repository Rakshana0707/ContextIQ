# ContextIQ Mobile Companion Application

React Native with Expo cross-platform companion application for the ContextIQ Behavioral Intelligence platform.

## Features

- **Hardware-Backed Security**: Encrypted session storage utilizing iOS Keychain and Android KeyStore via `expo-secure-store`.
- **Behavioral Dashboard**: Real-time Behavioral Friction Index (BFI), today's focus schedule, and circadian peak windows.
- **Task Management**: Create, complete, postpone, and prioritize tasks with empirical forgetting-risk predictions.
- **Adaptive Recommendations**: Contextual bandit interventions with LinUCB explanations and feedback tracking.
- **Intelligent Notifications**: Cognitive load shielding, quiet hours enforcement, and notification history.
- **Calendar Awareness**: Timeline view of external meetings, lunch breaks, and 15-minute post-meeting recovery buffers.
- **Workplace Geofencing**: Foreground contextual location reminders without continuous background battery drain.
- **Offline-First Synchronization**: Optimistic UI updates with an idempotent background mutation replay queue.

## Getting Started

### Prerequisites

- Node.js >= 18
- npm or yarn
- Expo CLI (`npx expo`)

### Running the App

```bash
cd mobile
npm install
npm start
```

### Running Tests

```bash
cd mobile
npm test
```
