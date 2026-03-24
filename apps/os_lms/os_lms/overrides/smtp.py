import smtplib

import frappe
from frappe import _
from frappe.email.oauth import Oauth
from frappe.email.smtp import SMTPServer
from frappe.utils import cint


def _custom_session(self):
    """Custom SMTP session override.

    Replaces the original SMTPServer.session property.
    """
    if self.is_session_active():
        return self._session

    SMTP = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

    try:
        _session = SMTP(self.server, self.port, timeout=self.timeout)
        if not _session:
            frappe.msgprint(
                _("Could not connect to outgoing email server"),
                raise_exception=frappe.OutgoingEmailError,
            )

        self.secure_session(_session)

        if self.use_oauth:
            Oauth(_session, self.email_account, self.login, self.access_token).connect()

        elif self.password:
            res = _session.login(str(self.login or ""), str(self.password or ""))

            # check if logged correctly
            if res[0] != 235:
                frappe.msgprint(res[1], raise_exception=frappe.OutgoingEmailError)

        # Re-issue EHLO after AUTH to refresh server capabilities
        # _session.ehlo() Removed because session closed after this command

        self._session = _session
        self._enqueue_connection_closure()
        return self._session

    except smtplib.SMTPAuthenticationError:
        self.throw_invalid_credentials_exception(email_account=self.email_account)

    except OSError as e:
        # Invalid mail server -- due to refusing connection
        frappe.throw(
            _("Invalid Outgoing Mail Server or Port: {0}").format(str(e)),
            title=_("Incorrect Configuration"),
        )


SMTPServer.session = property(_custom_session)
