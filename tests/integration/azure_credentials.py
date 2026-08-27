"""Shared ``TokenCredential`` test double for the Azure App Configuration and Key Vault
integration suites.

Kept out of any ``conftest.py`` so both fixtures and test modules can import it directly —
importing from a conftest module is not a supported pytest pattern.
"""

from azure.core.credentials import AccessToken, TokenCredential


class NoopCredential(TokenCredential):
    """A ``TokenCredential`` that returns a dummy token.

    Accepted by emulators/test doubles running with anonymous auth enabled, which don't
    validate the token value — only that a credential object was supplied.
    """

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:  # noqa: ARG002
        return AccessToken("Dummy", 9999999999)
