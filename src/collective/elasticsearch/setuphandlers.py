from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    @staticmethod
    def getNonInstallableProfiles():  # NOQA C0103
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "collective.elasticsearch:uninstall",
        ]


def post_install(context):  # NOQA W0613
    """Post install script"""
    # Do something at the end of the installation of this package.


def post_content(context):  # NOQA W0613
    """Post content script"""


def uninstall(context):  # NOQA W0613
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
