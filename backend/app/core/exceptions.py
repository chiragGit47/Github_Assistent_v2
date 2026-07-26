class GitHubAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}

        super().__init__(message)