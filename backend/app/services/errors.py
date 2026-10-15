class DomainError(Exception):
    """Business-rule violation. `code` is a stable id translated by bot / Mini App (err.<code>)."""

    def __init__(self, code: str, status: int = 400, commit: bool = False, **params):
        super().__init__(code)
        self.code = code
        self.status = status
        self.params = params
        # True: the unit of work still commits (e.g. a failed delivery-code attempt must be counted).
        self.commit = commit


def not_found() -> DomainError:
    return DomainError("not_found", 404)


def forbidden() -> DomainError:
    return DomainError("forbidden", 403)
