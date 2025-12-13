# Frontend Application

Một ứng dụng React hiệu suất cao với TypeScript, Tailwind CSS, và các công cụ modern.

## 🚀 Giới thiệu

Frontend này cung cấp một user interface toàn diện hỗ trợ:

- **React 19** - UI library hiện đại
- **TypeScript** - Type-safe development
- **Vite** - Build tool nhanh
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **React Query** - Data fetching & caching
- **Radix UI** - Headless UI components
- **Jotai** - State management
- **i18n** - Internationalization (Multi-language)
- **React Hook Form** - Form handling
- **Zod** - Schema validation
- **Sonner** - Toast notifications

## 📋 Yêu cầu

- Node.js 18+
- npm hoặc yarn hoặc pnpm

## 🔧 Cài đặt

### 1. Clone repository

```bash
cd frontend
```

### 2. Cài đặt dependencies

```bash
npm install
# hoặc
yarn install
# hoặc
pnpm install
```

### 3. Tạo environment file

```bash
cp .env.example .env
# Chỉnh sửa .env với API endpoint của bạn
```

## 🏃 Chạy ứng dụng

### Development mode

```bash
npm run dev
```

Ứng dụng sẽ chạy tại `http://localhost:5173`

### Build for production

```bash
npm run build
```

### Preview production build

```bash
npm run preview
```

### Lint code

```bash
npm run lint
```

## 📁 Cấu trúc dự án

```
frontend/
├── src/
│   ├── assets/              # Hình ảnh, fonts, media
│   ├── components/          # React components
│   │   ├── ui/             # UI components (Radix UI + Tailwind)
│   │   └── ...             # Custom components
│   ├── config/             # Cấu hình ứng dụng
│   │   ├── api.ts          # Axios config
│   │   ├── i18n.ts         # i18n setup
│   │   └── ...
│   ├── contexts/           # React contexts
│   │   └── AuthProvider    # Authentication context
│   ├── hooks/              # Custom React hooks
│   ├── layouts/            # Layout components
│   │   ├── MainLayout.tsx
│   │   └── AuthLayout.tsx
│   ├── locales/            # Translation files
│   │   ├── en/
│   │   ├── vi/
│   │   └── ...
│   ├── lib/                # Utilities & helpers
│   │   ├── api/            # API client
│   │   ├── utils.ts        # Utility functions
│   │   └── token-storage.ts
│   ├── pages/              # Page components
│   ├── queries/            # React Query hooks
│   ├── services/           # API services
│   ├── store/              # Jotai atoms (state)
│   ├── types/              # TypeScript types
│   ├── App.tsx             # Main App component
│   ├── App.css             # Global styles
│   └── main.tsx            # Entry point
├── public/                 # Static assets
│   ├── audio-processor-worklet.js
│   └── libopus.js
├── package.json            # Dependencies
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript config
├── tsconfig.app.json       # App TypeScript config
├── tsconfig.node.json      # Node TypeScript config
├── eslint.config.js        # ESLint config
├── components.json         # shadcn/ui config
├── tailwind.config.js      # Tailwind config
├── index.html              # HTML template
└── .env.example            # Environment variables template
```

## ⚙️ Environment Variables

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api

# Application
VITE_APP_NAME=Your App Name
VITE_APP_VERSION=1.0.0
```

## 🧩 Key Technologies

### UI & Styling

- **React** - Component library
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Radix UI** - Accessible UI primitives
- **Lucide React** - Icon library
- **shadcn/ui** - Component library built on Radix UI

### State Management

- **Jotai** - Primitive and flexible state management
- **React Query** - Server state management
- **React Context** - Local state

### Forms & Validation

- **React Hook Form** - Form management
- **Zod** - TypeScript-first schema validation

### Routing

- **React Router v7** - Client-side routing

### Internationalization

- **i18next** - Localization framework
- **react-i18next** - React integration

### API & Data

- **Axios** - HTTP client
- **React Query** - Data fetching, caching

### Others

- **Sonner** - Toast notifications
- **cmdk** - Command menu
- **js-cookie** - Cookie handling
- **react-markdown** - Markdown rendering

## 🎯 Features

### Authentication

- JWT token-based authentication
- Automatic token refresh
- Auth context management
- Protected routes

### State Management

- Global state with Jotai atoms
- Local component state
- Server state with React Query

### API Integration

- Centralized Axios instance
- Interceptors for authentication
- Error handling
- Request/response transformation

### i18n Support

- Multi-language support
- Language detection
- Translation management

### UI Components

- Pre-built UI components
- Consistent design system
- Tailwind CSS utility classes
- Accessible components (Radix UI)

## 🚀 Development Best Practices

### Code Organization

- Separate concerns (components, hooks, services)
- Type-safe with TypeScript
- Reusable components
- Utility functions in lib/

### Component Structure

```tsx
// With types
interface Props {
  title: string;
  onAction: () => void;
}

export function MyComponent({ title, onAction }: Props) {
  return <div>{title}</div>;
}
```

### Custom Hooks

```tsx
// hooks/useCustom.ts
export function useCustom() {
  // Hook logic
}
```

### API Services

```tsx
// services/userService.ts
export const userService = {
  getUser: (id: string) => apiClient.get(`/users/${id}`),
  updateUser: (id: string, data: any) => apiClient.post(`/users/${id}`, data),
};
```

## 📝 Scripts

```bash
npm run dev        # Start development server
npm run build      # Build for production
npm run preview    # Preview production build
npm run lint       # Lint code with ESLint
```

## 🔌 API Integration

### Axios Configuration

- Base URL: `/api`
- Proxy setup for development
- Automatic token injection in Authorization header
- Error handling & response parsing

### Token Management

- Stored in localStorage
- Automatically included in requests
- Refreshed on 401 responses

## 🧪 Testing

### Recommended tools

- **Vitest** - Fast unit test framework
- **React Testing Library** - Component testing
- **Playwright** - E2E testing

## 📚 Project Architecture

### Layered Structure

1. **Pages** - Route-level components
2. **Layouts** - Shared layout templates
3. **Components** - Reusable UI components
4. **Services** - API calls
5. **Hooks** - Custom React logic
6. **Store** - Global state (Jotai atoms)
7. **Types** - TypeScript definitions
8. **Utils** - Helper functions

### Data Flow

```
User Interaction
  ↓
Component
  ↓
Service/API
  ↓
React Query Cache
  ↓
Jotai Store
  ↓
UI Update
```

## 🎨 Styling

### Tailwind CSS

- Utility-first CSS framework
- Custom configuration in tailwind.config.js
- Supports dark mode
- Responsive design

### Theme Customization

Edit `tailwind.config.js` để customize:

- Colors
- Typography
- Spacing
- Breakpoints

## 🌍 i18n Configuration

### Add Translation

1. Create files in `src/locales/`:

   - `src/locales/en/translation.json`
   - `src/locales/vi/translation.json`

2. Use in components:

```tsx
import { useTranslation } from "react-i18next";

export function MyComponent() {
  const { t } = useTranslation();
  return <div>{t("key")}</div>;
}
```

## 🤝 Contributing

1. Tạo feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "feat: your message"`
3. Push to branch: `git push origin feature/your-feature`
4. Mở Pull Request

## 📄 License

Xem file LICENSE để biết chi tiết.

## 📞 Support

Nếu có vấn đề, vui lòng mở issue hoặc liên hệ team phát triển.
