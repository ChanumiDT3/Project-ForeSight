/**
 * Application routes. Screen access follows the backend-resolved role
 * (navigation/roles.ts); the backend independently enforces every action.
 */
import { Route, Routes } from 'react-router-dom';
import { DirectoryProvider } from './auth/DirectoryContext';
import { UserProvider } from './auth/UserContext';
import WhoAreYouDialog from './auth/WhoAreYouDialog';
import AppLayout from './components/AppLayout';
import RequireRole from './components/RequireRole';
import { SCREEN_ROLES } from './navigation/roles';
import AlertDetailPage from './pages/AlertDetailPage';
import AlertQueuePage from './pages/AlertQueuePage';
import DashboardPage from './pages/DashboardPage';
import LandingRedirect from './pages/LandingRedirect';
import LogReadingPage from './pages/LogReadingPage';
import MachineDetailPage from './pages/machines/MachineDetailPage';
import MachineEditPage from './pages/machines/MachineEditPage';
import MachineRegisterPage from './pages/machines/MachineRegisterPage';
import MachinesPage from './pages/machines/MachinesPage';
import NotFoundPage from './pages/NotFoundPage';
import WorkOrderDetailPage from './pages/work-order/WorkOrderDetailPage';
import WorkOrdersPage from './pages/WorkOrdersPage';

// PUBLIC_INTERFACE
export default function App() {
  /** Root component: identity providers, popup, and routed screens. */
  return (
    <UserProvider>
      <DirectoryProvider>
        <WhoAreYouDialog />
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<LandingRedirect />} />
            <Route path="log-reading" element={<RequireRole roles={SCREEN_ROLES.logReading}><LogReadingPage /></RequireRole>} />
            <Route path="alerts" element={<RequireRole roles={SCREEN_ROLES.alerts}><AlertQueuePage /></RequireRole>} />
            <Route path="alerts/:alertId" element={<RequireRole roles={SCREEN_ROLES.alerts}><AlertDetailPage /></RequireRole>} />
            <Route path="work-orders" element={<RequireRole roles={SCREEN_ROLES.workOrders}><WorkOrdersPage /></RequireRole>} />
            <Route
              path="work-orders/:workOrderId"
              element={<RequireRole roles={SCREEN_ROLES.workOrders}><WorkOrderDetailPage /></RequireRole>}
            />
            <Route path="machines" element={<RequireRole roles={SCREEN_ROLES.machines}><MachinesPage /></RequireRole>} />
            <Route path="machines/new" element={<RequireRole roles={SCREEN_ROLES.machineEdit}><MachineRegisterPage /></RequireRole>} />
            <Route path="machines/:machineId" element={<RequireRole roles={SCREEN_ROLES.machines}><MachineDetailPage /></RequireRole>} />
            <Route
              path="machines/:machineId/edit"
              element={<RequireRole roles={SCREEN_ROLES.machineEdit}><MachineEditPage /></RequireRole>}
            />
            <Route path="dashboard" element={<RequireRole roles={SCREEN_ROLES.dashboard}><DashboardPage /></RequireRole>} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </DirectoryProvider>
    </UserProvider>
  );
}
