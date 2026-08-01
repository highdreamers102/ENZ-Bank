import re

import streamlit as st
from streamlit_option_menu import option_menu

from bank import Bank
from utils import (
    generate_payment_qr,
    decode_payment_qr,
    export_csv,
    export_json,
    export_txt,
    export_pdf,
)

bank = Bank()



st.set_page_config(
    page_title="ENZ BANK",
    page_icon="🏦",
    layout="wide"
)

st.markdown(
    """
    <style>
        .stApp { background-color: #0b1220; }
        h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown { color: #e8edf5; }
        .enz-hero {
            background: linear-gradient(135deg, #0f4c81 0%, #16324f 100%);
            padding: 28px 32px;
            border-radius: 16px;
            margin-bottom: 24px;
            border: 1px solid #1f3a5f;
        }
        .enz-hero h1 { margin: 0; font-size: 2.1rem; }
        .enz-hero p { margin: 6px 0 0 0; opacity: 0.85; }
        .enz-card {
            background: #111a2b;
            border: 1px solid #223252;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 14px;
        }
        div[data-testid="stMetric"] {
            background: #111a2b;
            border: 1px solid #223252;
            border-radius: 12px;
            padding: 14px;
        }
        .stButton>button {
            border-radius: 10px;
            border: 1px solid #1f3a5f;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

for key, default in {
    "logged_in": False,
    "user": None,
    "is_admin": False,
    "nav_target": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def go_to(page_name):
    """Programmatically switch the sidebar menu to `page_name` and rerun."""
    st.session_state.nav_target = page_name
    st.rerun()


def refresh_user():
    """Re-fetch the logged-in user's row so balances shown are always current."""
    if st.session_state.user:
        st.session_state.user = bank.show_details_streamlit(
            st.session_state.user["account_number"], None
        ) or st.session_state.user



st.markdown(
    """
    <div class="enz-hero">
        <h1>🏦 ENZ Bank</h1>
        <p>Secure • Fast • Reliable Banking</p>
    </div>
    """,
    unsafe_allow_html=True,
)


if st.session_state.is_admin:
    menu_options = ["Admin Dashboard", "Manage Accounts", "Action Log", "Admin Logout"]
    menu_icons = ["speedometer2", "shield-check", "journal-text", "box-arrow-right"]
elif st.session_state.logged_in:
    menu_options = [
        "Dashboard",
        "My Profile",
        "Wallet",
        "My QR Code",
        "Scan & Pay",
        "Check Balance",
        "Deposit Money",
        "Withdraw Money",
        "Transfer Money",
        "UPI Transfer",
        "Mobile Recharge",
        "Transaction History",
        "Delete Account",
        "Logout",
    ]
    menu_icons = [
        "speedometer2", "person-circle", "wallet2", "qr-code", "camera",
        "cash-stack", "cash-coin", "dash-circle", "arrow-left-right",
        "send", "phone", "clock-history", "trash", "box-arrow-right",
    ]
else:
    menu_options = ["Home", "Login", "Create Account", "Admin Login", "Contact", "About"]
    menu_icons = ["house", "person", "person-plus", "shield-lock", "telephone", "info-circle"]

manual_select = None
if st.session_state.nav_target in menu_options:
    manual_select = menu_options.index(st.session_state.nav_target)
st.session_state.nav_target = None

with st.sidebar:
    selected = option_menu(
        menu_title="ENZ Bank",
        options=menu_options,
        icons=menu_icons,
        default_index=0,
        manual_select=manual_select,
        key="enz_menu",
    )


if selected == "Home":
    st.subheader("Welcome to ENZ Bank")
    st.write(
        "Manage your money securely with a modern banking experience. "
        "Create an account, access your dashboard, transfer money, and view "
        "transactions effortlessly."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Login", use_container_width=True):
            go_to("Login")
    with col2:
        if st.button("🆕 Create Account", use_container_width=True):
            go_to("Create Account")

    st.divider()
    st.subheader("✨ Our Features")
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        st.success("✔ Secure Banking")
        st.success("✔ Instant Money Transfer (IFSC verified)")
        st.success("✔ Digital Wallet & Scan-to-Pay")
        st.success("✔ Transaction History")
    with fcol2:
        st.success("✔ 24×7 Banking")
        st.success("✔ PIN Protected Accounts")
        st.success("✔ Easy Account Management")
        st.success("✔ Downloadable Statements (CSV/PDF/JSON/TXT)")

    st.divider()
    st.caption("© 2026 ENZ Bank | Banking Made Simple")





elif selected == "Create Account":
    st.header("Create Account")

    with st.form("create_account_form"):
        name = st.text_input("Full Name *", placeholder="Enter your full name")
        age = st.number_input("Age *", min_value=18, max_value=120, step=1)
        email = st.text_input("Email *", placeholder="yourname@gmail.com")
        mobile = st.text_input("Mobile Number *", placeholder="10-digit mobile number (used for your UPI ID)")
        address = st.text_area("Address *", placeholder="House No, Street, City, State, PIN Code")
        pin = st.text_input("4-Digit PIN *", placeholder="Enter your PIN", type="password")

        submit = st.form_submit_button("Create Account")

        if submit:
            name_clean = (name or "").strip()
            email_clean = (email or "").strip().lower()
            mobile_clean = (mobile or "").strip()
            address_clean = (address or "").strip()
            pin_clean = (pin or "").strip()

            if not re.fullmatch(r"[A-Za-z ]{3,}", name_clean):
                st.error("Name should contain only letters/spaces and be at least 3 characters.")
            elif not re.fullmatch(r"[a-zA-Z0-9._%+-]+@gmail\.com", email_clean):
                st.error("Please enter a valid Gmail address.")
            elif not re.fullmatch(r"[6-9]\d{9}", mobile_clean):
                st.error("Enter a valid 10-digit Indian mobile number.")
            elif address_clean == "":
                st.error("Address is required.")
            elif not pin_clean.isdigit() or len(pin_clean) != 4:
                st.error("PIN must contain exactly 4 digits.")
            else:
                user_data = {
                    "name": name_clean,
                    "age": age,
                    "email": email_clean,
                    "mobile_number": mobile_clean,
                    "address": address_clean,
                    "pin": pin_clean,
                }
                success, result = bank.create_account_streamlit(user_data)

                if success:
                    st.success("Account Created Successfully 🎉")
                    st.write("### Account Details")
                    st.write(f"**Account Number:** {result['account_number']}")
                    st.write(f"**IFSC Code:** {result['IFSC_code']}")
                    st.write(f"**UPI ID:** {result['upi_id']}")
                    st.write(f"**Balance:** ₹{result['balance']}")
                    st.info("Save your account number and PIN — you'll need them to log in.")
                else:
                    st.error(result)




elif selected == "Login":
    st.header("Customer Login")
    account_number = st.text_input("Account Number")
    pin = st.text_input("PIN", type="password")

    if st.button("Login"):
        success, account = bank.login_streamlit(account_number, pin)
        if success:
            st.session_state.logged_in = True
            st.session_state.user = account
            st.success("Login Successful")
            go_to("Dashboard")
        else:
            st.error(account)


elif selected == "Admin Login":
    st.header("Admin Login")
    username = st.text_input("Admin Username")
    password = st.text_input("Admin Password", type="password")

    if st.button("Login as Admin"):
        success, result = bank.admin_login_streamlit(username, password)
        if success:
            st.session_state.is_admin = True
            st.success("Admin login successful")
            go_to("Admin Dashboard")
        else:
            st.error(result)


elif selected == "Contact":
    st.header("Contact Us")
    st.write("📍 **Address:** ENZ Bank Head Office, India")
    st.write("📞 **Phone:** +91-XXXXXXXXXX")
    st.write("✉ **Email:** support@enzbank.com")


elif selected == "About":
    st.header("About ENZ Bank")
    st.write(
        """
        ENZ Bank is a simple banking management system built using Python, Streamlit,
        and a real SQL database (SQLite).

        It lets users create an account, deposit and withdraw money, transfer funds
        to other account holders (with IFSC verification), top up and pay from a
        digital wallet, scan-and-pay via QR code, and download their transaction
        history in multiple formats — all in one easy-to-use dashboard.
        """
    )




elif selected == "Dashboard":
    refresh_user()
    user = st.session_state.user

    header_col1, header_col2 = st.columns([1, 5])
    with header_col1:
        if user.get("profile_photo_path"):
            st.image(user["profile_photo_path"], width=90)
        else:
            st.markdown("### 👤")
    with header_col2:
        st.header("Dashboard")
        st.success(f"Welcome back, {user['name']} 👋")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Account Number", user["account_number"])
    with c2:
        st.metric("IFSC Code", user.get("ifsc_code", ""))
    with c3:
        st.metric("Bank Balance", f"₹{user['balance']:.2f}")
    with c4:
        st.metric("Wallet Balance", f"₹{user.get('wallet_balance', 0):.2f}")

    if user.get("upi_id"):
        st.caption(f"UPI ID: **{user['upi_id']}**")

    st.info("Use the sidebar menu to deposit, withdraw, transfer, top up your wallet, or scan & pay.")


elif selected == "Wallet":
    refresh_user()
    user = st.session_state.user
    st.header("💳 Wallet")

    success, wallet_balance = bank.get_wallet_balance_streamlit(user["account_number"], None)
    st.metric("Wallet Balance", f"₹{user.get('wallet_balance', 0):.2f}")
    st.metric("Bank Balance", f"₹{user['balance']:.2f}")

    tab1, tab2 = st.tabs(["Add Money to Wallet", "Withdraw to Bank"])

    with tab1:
        pin1 = st.text_input("PIN", type="password", key="topup_pin")
        amt1 = st.number_input("Amount", min_value=1.0, key="topup_amt")
        if st.button("Add to Wallet"):
            success, message = bank.wallet_topup_streamlit(user["account_number"], pin1, amt1)
            (st.success if success else st.error)(message)
            if success:
                refresh_user()

    with tab2:
        pin2 = st.text_input("PIN", type="password", key="wd_pin")
        amt2 = st.number_input("Amount", min_value=1.0, key="wd_amt")
        if st.button("Withdraw to Bank"):
            success, message = bank.wallet_withdraw_streamlit(user["account_number"], pin2, amt2)
            (st.success if success else st.error)(message)
            if success:
                refresh_user()


elif selected == "My QR Code":
    user = st.session_state.user
    st.header("📱 My QR Code")
    st.write("Share this QR code with others so they can pay you directly to your wallet.")
    qr_bytes = generate_payment_qr(user["account_number"])
    st.image(qr_bytes, width=260)
    st.download_button("Download QR Code", data=qr_bytes, file_name="enzbank_qr.png", mime="image/png")
    st.caption(f"Account Number: {user['account_number']}")


elif selected == "Scan & Pay":
    user = st.session_state.user
    st.header("📷 Scan & Pay")
    st.write("Upload a QR code image (someone else's ENZ Bank QR) to pay them from your wallet.")

    uploaded = st.file_uploader("Upload QR Code Image", type=["png", "jpg", "jpeg"])

    if uploaded is not None:
        account_number, error = decode_payment_qr(uploaded.read())
        if error:
            st.error(error)
        else:
            payee_name = bank.lookup_account_name(account_number)
            if not payee_name:
                st.error("This account no longer exists.")
            else:
                st.success(f"Paying: **{payee_name}** ({account_number})")
                pin = st.text_input("Your PIN", type="password", key="scanpay_pin")
                amount = st.number_input("Amount", min_value=1.0, key="scanpay_amt")
                if st.button("Pay Now"):
                    success, message = bank.wallet_pay_streamlit(
                        user["account_number"], pin, account_number, amount
                    )
                    (st.success if success else st.error)(message)
                    if success:
                        refresh_user()


elif selected == "Check Balance":
    st.header("Check Balance")
    account_number = st.text_input("Account Number")
    pin = st.text_input("PIN", type="password")

    if st.button("Check Balance"):
        success, balance = bank.check_balance_streamlit(account_number, pin)
        (st.success(f"Current Balance: ₹{balance}") if success else st.error(balance))


elif selected == "Deposit Money":
    st.header("Deposit Money")
    account_number = st.text_input("Account Number")
    pin = st.text_input("PIN", type="password")
    amount = st.number_input("Amount", min_value=1.0)

    if st.button("Deposit"):
        success, message = bank.deposit_streamlit(account_number, pin, amount)
        (st.success if success else st.error)(message)
        if success:
            refresh_user()


elif selected == "Withdraw Money":
    st.header("Withdraw Money")
    account_number = st.text_input("Account Number")
    pin = st.text_input("PIN", type="password")
    amount = st.number_input("Amount", min_value=1.0)

    if st.button("Withdraw"):
        success, message = bank.withdraw_streamlit(account_number, pin, amount)
        (st.success if success else st.error)(message)
        if success:
            refresh_user()


elif selected == "Transfer Money":
    st.header("Transfer Money")
    st.caption("Direct transfers to other ENZ Bank accounts, verified by IFSC code.")

    sender_account = st.text_input("Your Account Number")
    sender_pin = st.text_input("Your PIN", type="password")
    receiver_account = st.text_input("Receiver Account Number")
    receiver_ifsc = st.text_input("Receiver IFSC Code", placeholder="e.g. ENZB0000001")
    amount = st.number_input("Amount", min_value=1.0, step=1.0)

    if st.button("Transfer"):
        success, message = bank.transfer_streamlit(
            sender_account, sender_pin, receiver_account, amount, receiver_ifsc
        )
        (st.success if success else st.error)(message)
        if success:
            refresh_user()


elif selected == "UPI Transfer":
    st.header("⚡ UPI Transfer")
    st.caption("Send money instantly using a UPI ID or mobile number — no IFSC needed.")

    sender_account = st.text_input("Your Account Number")
    sender_pin = st.text_input("Your PIN", type="password")
    recipient = st.text_input("Recipient UPI ID or Mobile Number", placeholder="e.g. 9876543210 or 9876543210@enzbank")
    amount = st.number_input("Amount", min_value=1.0, step=1.0)

    if st.button("Send"):
        success, message = bank.upi_transfer_streamlit(sender_account, sender_pin, recipient, amount)
        (st.success if success else st.error)(message)
        if success:
            refresh_user()


elif selected == "Mobile Recharge":
    user = st.session_state.user
    st.header("📱 Mobile Recharge")

    pin = st.text_input("PIN", type="password")
    recharge_mobile = st.text_input("Mobile Number to Recharge", value=user.get("mobile_number") or "")
    operator = st.selectbox("Operator", ["Jio", "Airtel", "Vi", "BSNL"])
    amount = st.number_input("Recharge Amount", min_value=10.0, step=10.0)
    source = st.radio("Pay from", ["Bank Balance", "Wallet"], horizontal=True)

    if st.button("Recharge Now"):
        success, message = bank.mobile_recharge_streamlit(
            user["account_number"], pin, recharge_mobile, operator, amount,
            source="wallet" if source == "Wallet" else "bank",
        )
        (st.success if success else st.error)(message)
        if success:
            refresh_user()


elif selected == "Transaction History":
    user = st.session_state.user
    st.header("Transaction History")
    st.caption(f"Showing history for account {user['account_number']} only.")

    pin = st.text_input("Confirm PIN to view history", type="password")

    if st.button("View History") or "history_cache" in st.session_state:
        success, result = bank.transaction_history_streamlit(user["account_number"], pin)
        if success:
            st.session_state.history_cache = result
        else:
            st.error(result)
            st.session_state.pop("history_cache", None)

    if "history_cache" in st.session_state:
        result = st.session_state.history_cache
        if len(result) == 0:
            st.info("No Transactions Found.")
        else:
            for t in result:
                with st.container():
                    st.markdown(
                        f"""<div class="enz-card">
                        <b>{t['type']}</b> — ₹{t['amount']:.2f}<br>
                        Balance after: ₹{t['balance_after']:.2f}<br>
                        {t.get('description', 'N/A')}<br>
                        <span style="opacity:0.7">{t.get('date','')} {t.get('date_time','')}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            st.divider()
            st.subheader("⬇ Download Statement")
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.download_button("CSV", data=export_csv(result), file_name="transactions.csv", mime="text/csv")
            with d2:
                st.download_button("JSON", data=export_json(result), file_name="transactions.json", mime="application/json")
            with d3:
                st.download_button("TXT", data=export_txt(result), file_name="transactions.txt", mime="text/plain")
            with d4:
                st.download_button(
                    "PDF",
                    data=export_pdf(result, user["account_number"]),
                    file_name="transactions.pdf",
                    mime="application/pdf",
                )


elif selected == "My Profile":
    refresh_user()
    user = st.session_state.user
    st.header("👤 My Profile")
    st.caption("Only you can edit your profile — the bank/admin can never modify this data.")

    pcol1, pcol2 = st.columns([1, 3])
    with pcol1:
        if user.get("profile_photo_path"):
            st.image(user["profile_photo_path"], width=140)
        else:
            st.markdown("#### No photo yet")
    with pcol2:
        st.write(f"**Name:** {user['name']}")
        st.write(f"**Account Number:** {user['account_number']}")
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Mobile:** {user.get('mobile_number') or 'Not set'}")
        st.write(f"**UPI ID:** {user.get('upi_id') or 'Not set'}")
        st.write(f"**Address:** {user['address']}")

    st.divider()
    st.subheader("Edit Profile")

    photo = st.file_uploader("Upload / change profile photo", type=["png", "jpg", "jpeg"])
    pin = st.text_input("Confirm PIN to save changes", type="password")
    name = st.text_input("New Name", placeholder="Leave blank to keep current")
    email = st.text_input("New Email", placeholder="Leave blank to keep current")
    mobile = st.text_input("New Mobile Number", placeholder="Leave blank to keep current (changes your UPI ID too)")
    address = st.text_area("New Address", placeholder="Leave blank to keep current")

    if st.button("Save Changes"):
        photo_bytes = None
        photo_ext = "png"
        if photo is not None:
            photo_bytes = photo.read()
            photo_ext = photo.name.split(".")[-1].lower()

        success, message = bank.update_profile_streamlit(
            user["account_number"], pin,
            name=name, email=email, address=address,
            mobile_number=mobile, photo_bytes=photo_bytes, photo_ext=photo_ext,
        )
        (st.success if success else st.error)(message)
        if success:
            refresh_user()
            st.rerun()


elif selected == "Delete Account":
    user = st.session_state.user
    st.header("⚠ Delete Account")
    st.warning("This action is permanent and cannot be undone.")
    pin = st.text_input("Confirm PIN", type="password")

    if st.button("Delete My Account"):
        success, message = bank.delete_account_streamlit(user["account_number"], pin)
        if success:
            st.success(message)
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()
        else:
            st.error(message)


elif selected == "Logout":
    st.session_state.logged_in = False
    st.session_state.user = None
    st.success("Logged Out Successfully")
    st.rerun()





elif selected == "Admin Dashboard":
    st.header("🛡 Admin Dashboard")
    st.caption("View-only. Admin can never edit customer profile data, PINs, or balances directly.")
    data = bank.admin_streamlit()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Accounts", data["total_accounts"])
    c2.metric("Total Bank Balance", f"₹{data['total_balance']}")
    c3.metric("Total Wallet Balance", f"₹{data['total_wallet_balance']}")

    st.write("## All Accounts")
    for account in data["accounts"]:
        status = account.get("status", "active")
        badge = {"active": "🟢", "frozen": "🟡", "suspended": "🔴"}.get(status, "⚪")
        st.markdown(
            f"""<div class="enz-card">
            <b>{account['name']}</b> {badge} <i>{status}</i><br>
            Account: {account['account_number']} &nbsp;|&nbsp; IFSC: {account['ifsc_code']}<br>
            Mobile: {account.get('mobile_number') or 'N/A'} &nbsp;|&nbsp; UPI: {account.get('upi_id') or 'N/A'}<br>
            Bank Balance: ₹{account['balance']:.2f} &nbsp;|&nbsp; Wallet: ₹{account['wallet_balance']:.2f}
            </div>""",
            unsafe_allow_html=True,
        )


elif selected == "Manage Accounts":
    st.header("🛡 Manage Accounts")
    st.caption(
        "Admin can freeze, suspend, resume, or delete an account — but can never "
        "edit a customer's name, email, address, mobile, PIN, or balance."
    )
    data = bank.admin_streamlit()

    account_number = st.selectbox(
        "Select an account",
        options=[a["account_number"] for a in data["accounts"]],
        format_func=lambda acc: next(
            f"{a['name']} — {acc} ({a['status']})" for a in data["accounts"] if a["account_number"] == acc
        ),
    )

    selected_account = next((a for a in data["accounts"] if a["account_number"] == account_number), None)

    if selected_account:
        st.markdown(
            f"""<div class="enz-card">
            <b>{selected_account['name']}</b><br>
            Account: {selected_account['account_number']} &nbsp;|&nbsp; Status: <b>{selected_account['status']}</b><br>
            Bank Balance: ₹{selected_account['balance']:.2f} &nbsp;|&nbsp; Wallet: ₹{selected_account['wallet_balance']:.2f}
            </div>""",
            unsafe_allow_html=True,
        )

        admin_username = "admin"  

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🟡 Freeze", use_container_width=True):
                success, message = bank.admin_freeze_account(admin_username, account_number)
                (st.success if success else st.error)(message)
        with b2:
            if st.button("🟢 Unfreeze", use_container_width=True):
                success, message = bank.admin_unfreeze_account(admin_username, account_number)
                (st.success if success else st.error)(message)
        with b3:
            if st.button("🔴 Suspend", use_container_width=True):
                success, message = bank.admin_suspend_account(admin_username, account_number)
                (st.success if success else st.error)(message)
        with b4:
            if st.button("▶ Resume", use_container_width=True):
                success, message = bank.admin_resume_account(admin_username, account_number)
                (st.success if success else st.error)(message)

        st.divider()
        st.warning("Deleting an account is permanent and removes its transaction history.")
        confirm_delete = st.checkbox(f"I confirm I want to permanently delete account {account_number}")
        if st.button("🗑 Delete Account", disabled=not confirm_delete):
            success, message = bank.admin_delete_account(admin_username, account_number)
            (st.success if success else st.error)(message)
            if success:
                st.rerun()


elif selected == "Action Log":
    st.header("📋 Admin Action Log")
    st.caption("Every freeze/suspend/resume/delete action taken by an admin is recorded here.")
    logs = bank.admin_action_log_streamlit()
    if not logs:
        st.info("No admin actions recorded yet.")
    else:
        for entry in logs:
            st.markdown(
                f"""<div class="enz-card">
                <b>{entry['action']}</b> — Account {entry['account_number']}<br>
                By: {entry['admin_username']} &nbsp;|&nbsp; {entry['date']} {entry['time']}
                </div>""",
                unsafe_allow_html=True,
            )


elif selected == "Admin Logout":
    st.session_state.is_admin = False
    st.success("Admin logged out")
    st.rerun()







