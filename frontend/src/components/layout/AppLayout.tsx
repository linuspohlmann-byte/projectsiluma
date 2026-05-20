import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { AppHeader } from './AppHeader';
import { BottomNav } from './BottomNav';
import { CoursePicker } from './CoursePicker';

export function AppLayout() {
  const [courseOpen, setCourseOpen] = useState(false);

  return (
    <div className="flex min-h-dvh flex-col pb-24 md:pb-0">
      <AppHeader onCourseClick={() => setCourseOpen(true)} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-4">
        <Outlet />
      </main>
      <BottomNav />
      <CoursePicker open={courseOpen} onClose={() => setCourseOpen(false)} />
    </div>
  );
}
