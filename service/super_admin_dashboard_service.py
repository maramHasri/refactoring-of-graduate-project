from repositories.super_admin_dashboard_repository import SuperAdminDashboardRepository


class SuperAdminDashboardService:
    def __init__(self):
        self.repo = SuperAdminDashboardRepository()

    def get_dashboard(self) -> dict:
        return self.repo.build_dashboard()
