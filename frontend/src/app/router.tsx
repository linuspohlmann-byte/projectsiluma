import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LoginPage } from '@/features/auth/LoginPage';
import { LibraryPage } from '@/features/library/LibraryPage';
import { BrowsePage } from '@/features/browse/BrowsePage';
import { CoursesPage } from '@/features/courses/CoursesPage';
import { WordsPage } from '@/features/words/WordsPage';
import { LessonPage } from '@/features/lesson/LessonPage';
import { PracticePage } from '@/features/practice/PracticePage';
import { EvaluationPage } from '@/features/evaluation/EvaluationPage';
import { AlphabetPage } from '@/features/alphabet/AlphabetPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { OnboardingPage } from '@/features/onboarding/OnboardingPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/library" replace /> },
          { path: 'library', element: <LibraryPage /> },
          { path: 'browse', element: <BrowsePage /> },
          { path: 'courses', element: <CoursesPage /> },
          { path: 'words', element: <WordsPage /> },
          { path: 'practice', element: <PracticePage /> },
          { path: 'alphabet', element: <AlphabetPage /> },
          { path: 'settings', element: <SettingsPage /> },
          { path: 'onboarding', element: <OnboardingPage /> },
        ],
      },
      { path: 'lesson/:levelId', element: <LessonPage /> },
      { path: 'evaluation/:levelId', element: <EvaluationPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/library" replace /> },
]);
