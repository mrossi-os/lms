from frappe.email.doctype.email_account.email_account import EmailAccount
import os


class CustomEmailAccount(EmailAccount):
    def get_smtp_server(self):
        server = super().get_smtp_server()
        if server and server.session:
            if(server.session.esmtp_features["size"] == "0"):
                server.session.esmtp_features["size"] = "1000000"
        print("OKKKKK")
        return server