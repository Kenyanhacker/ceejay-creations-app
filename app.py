import os
import sqlite3
import pandas as pd
from datetime import datetime
import streamlit as st

# ReportLab Imports for Professional PDF Generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# SECURE STORAGE PATH CONFIGURATION
# ==========================================
# If running on Streamlit Cloud, write to the persistent /data folder
if os.path.exists("/data"):
    DB_NAME = "/data/rider_market_system.db"
else:
    DB_NAME = "rider_market_system.db"

# ==========================================
# DATABASE LAYER
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS riders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            rider_id INTEGER,
            payment_date TEXT,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (rider_id, payment_date),
            FOREIGN KEY (rider_id) REFERENCES riders(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# ROBUST PDF GENERATION ENGINE
# ==========================================
def build_pdf_report(start_date_str, target_rider_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if target_rider_name:
        target_rider_name = target_rider_name.strip()

    if target_rider_name and target_rider_name not in ["Select Rider", "All Riders"]:
        cursor.execute("SELECT id, name FROM riders WHERE LOWER(name) = LOWER(?)", (target_rider_name,))
    else:
        cursor.execute("SELECT id, name FROM riders ORDER BY name ASC")
        
    riders = cursor.fetchall()
    
    if not riders:
        conn.close()
        return None, "No matching rider records found."

    pdf_path = "generated_report.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#10B981"), alignment=1)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=11, leading=16, textColor=colors.HexColor("#020617"))
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor("#020617"))
    table_text_style = ParagraphStyle('TableText', parent=styles['Normal'], fontSize=9, alignment=1)

    for page_num, (rider_id, name) in enumerate(riders, start=1):
        cursor.execute('''
            SELECT payment_date, amount FROM payments 
            WHERE rider_id = ? AND payment_date >= ? 
            ORDER BY payment_date ASC
        ''', (rider_id, start_date_str))
        records = cursor.fetchall()
        
        total_paid = sum(float(r[1]) for r in records if r[1])
        
        story.append(Paragraph("<b>RIDER DETAILS CONFIRMATION LETTER</b>", title_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Rider Name:</b> {name}", meta_style))
        story.append(Paragraph(f"<b>Aggregate Remittance:</b> KES {total_paid:,.2f}", meta_style))
        story.append(Spacer(1, 12))
        
        intro_text = (
            "This letter is issued to request you to carefully review and confirm the details recorded in our system. "
            "The purpose of this confirmation is to ensure accuracy and transparency before compiling final financial "
            "records and undertaking any debt collection processes. Failure to raise any discrepancies within the "
            "agreed time frame shall be taken as confirmation that the information provided is accurate. "
            "We appreciate your cooperation in avoiding any future misunderstandings."
        )
        story.append(Paragraph(intro_text, body_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Daily Payments Record (Dates starting {start_date_str})</b>", meta_style))
        story.append(Spacer(1, 8))
        
        if not records:
            story.append(Paragraph("<i>No payment history recorded from this date forward.</i>", body_style))
            story.append(Spacer(1, 20))
        else:
            for i in range(0, len(records), 13):
                chunk = records[i:i+13]
                date_headers = [Paragraph(f"<b>{r[0].split('-')[-1]}</b>", table_text_style) for r in chunk]
                payment_vals = [Paragraph(f"KES {float(r[1]):,.2f}" if r[1] else "KES 0.00", table_text_style) for r in chunk]
                
                table_data = [
                    [Paragraph("<b>Date</b>", table_text_style)] + date_headers,
                    [Paragraph("<b>Payment</b>", table_text_style)] + payment_vals
                ]
                
                t = Table(table_data, colWidths=[55] + [42]*len(chunk))
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#334155")),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))
        
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"Page {page_num} of {len(riders)}", ParagraphStyle('PageStyle', parent=styles['Normal'], alignment=2, fontSize=9, textColor=colors.gray)))
        
        if page_num < len(riders):
            from reportlab.platypus import PageBreak
            story.append(PageBreak())
            
    doc.build(story)
    conn.close()
    return pdf_path, "Success"

# ==========================================
# WEB APPLICATION UI LAYER (STREAMLIT)
# ==========================================
st.set_page_config(page_title="CeeJay Creations - Dashboard Suite", layout="wide", initial_sidebar_state="expanded")
init_db()

# Desktop-Matched Custom Look CSS Theme
st.markdown("""
    <style>
    .stApp { background-color: #020617; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0B0F19; border-right: 1px solid #1E293B; }
    div[data-testid="stMetricValue"] { color: #10B981 !important; }
    </style>
""", unsafe_allow_html=True)

# Fetch current dynamic rider array lists
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("SELECT name FROM riders ORDER BY name ASC")
all_riders = [r[0] for r in cursor.fetchall()]
conn.close()

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.title("CEEJAY CREATIONS")
    st.caption("Action Control Core")
    st.markdown("---")
    
    # 1. Add Rider Interface Module
    st.markdown("### Add New Rider Profile")
    new_rider_name = st.text_input("Rider Full Name", key="add_rider_input")
    if st.button("+ Add New Rider", use_container_width=True):
        if new_rider_name.strip():
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO riders (name) VALUES (?)", (new_rider_name.strip(),))
                conn.commit()
                st.success(f"Successfully added {new_rider_name}")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Rider record profile already exists.")
            finally:
                conn.close()
        else:
            st.warning("Please provide a valid name.")
            
    st.markdown("---")
    
    # 2. Record Payment Interface Module
    st.markdown("### Log Entry Payments")
    selected_rider = st.selectbox("Select Target Rider", ["Select Rider"] + all_riders)
    log_date = st.date_input("Transaction Date", datetime.today())
    payment_amount = st.text_input("Payment Amount (KES)", placeholder="e.g., 500")
    
    if st.button("💾 Save Entry Log", use_container_width=True):
        if selected_rider == "Select Rider":
            st.error("Please add and select an active driver account row.")
        else:
            try:
                amt_val = float(payment_amount.replace("KES", "").replace(",", "").strip())
                date_str = log_date.strftime('%Y-%m-%d')
                
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM riders WHERE name = ?", (selected_rider,))
                rider_id = cursor.fetchone()[0]
                
                cursor.execute('''
                    INSERT INTO payments (rider_id, payment_date, amount) VALUES (?, ?, ?)
                    ON CONFLICT(rider_id, payment_date) DO UPDATE SET amount=excluded.amount
                ''', (rider_id, date_str, amt_val))
                conn.commit()
                conn.close()
                st.success("Transaction metrics balanced securely.")
                st.rerun()
            except ValueError:
                st.error("Amount fields must contain valid decimal integers.")

    st.markdown("---")

    # 3. System Storage Backup Management Panel
    st.markdown("### Free Cloud Storage Vault")
    if os.path.exists(DB_NAME):
        with open(DB_NAME, "rb") as db_file:
            st.download_button(
                label="📥 Download System Database",
                data=db_file,
                file_name="rider_market_system.db",
                mime="application/octet-stream",
                use_container_width=True
            )
            
    uploaded_db = st.file_uploader("📤 Restore System Database File", type=["db"])
    if uploaded_db is not None:
        if st.button("🔄 Execute System Restore", use_container_width=True):
            with open(DB_NAME, "wb") as f:
                f.write(uploaded_db.getbuffer())
            st.success("Database restored successfully!")
            st.rerun()

# --- MAIN WORKSPACE ---
# Render KPIs Header Panel Cards
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(id) FROM riders")
count_riders = cursor.fetchone()[0]
cursor.execute("SELECT SUM(amount) FROM payments")
sum_revenue = cursor.fetchone()[0] or 0.0
conn.close()

kpi1, kpi2 = st.columns(2)
with kpi1:
    st.metric(label="TOTAL MANAGED RIDERS", value=str(count_riders))
with kpi2:
    st.metric(label="AGGREGATE REVENUE LEDGER (KES)", value=f"KES {sum_revenue:,.2f}")

st.markdown("---")

# Filters, Searches, and Toolbar Ribbon
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    search_filter = st.text_input("🔍 Filter Live View Identity...")
with col_f2:
    rep_rider = st.selectbox("Notice Targeting", ["All Riders"] + all_riders)
with col_f3:
    rep_date = st.date_input("Notice Filter Start Date", datetime(2026, 1, 1))

# Action Trigger Row
col_b1, col_b2, col_b3 = st.columns([2, 2, 2])
with col_b1:
    rep_date_str = rep_date.strftime('%Y-%m-%d')
    pdf_file, msg = build_pdf_report(rep_date_str, rep_rider)
    if pdf_file and os.path.exists(pdf_file):
        with open(pdf_file, "rb") as f:
            st.download_button(
                label="📄 Download PDF Notice",
                data=f,
                file_name=f"Rider_Notice_{rep_rider}_{rep_date_str}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.button("📄 PDF Notice (Empty Filters)", disabled=True, use_container_width=True)

with col_b2:
    # CSV Core Database Query Logic
    conn = sqlite3.connect(DB_NAME)
    csv_query = '''
        SELECT r.name as 'Rider Name', p.payment_date as 'Payment Date', p.amount as 'Amount Received (KES)'
        FROM payments p JOIN riders r ON p.rider_id = r.id 
        WHERE p.payment_date >= ? ORDER BY r.name ASC, p.payment_date ASC
    '''
    csv_df = pd.read_sql_query(csv_query, conn, params=(rep_date_str,))
    conn.close()
    
    st.download_button(
        label="📊 Export Spreadsheet CSV",
        data=csv_df.to_csv(index=False).encode('utf-8'),
        file_name=f"Rider_Market_Ledger_{rep_date_str}.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_b3:
    # 4. Purge Profile Actions Selector Dropdown
    purge_target = st.selectbox("Purge Target Account Selection", ["Select Profile to Delete"] + all_riders, label_visibility="collapsed")
    if st.button("🗑️ Purge Rider Profile", use_container_width=True, type="primary"):
        if purge_target != "Select Profile to Delete":
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM riders WHERE name = ?", (purge_target,))
            conn.commit()
            conn.close()
            st.warning(f"Purged profile metric history logs for '{purge_target}'.")
            st.rerun()
        else:
            st.error("Please pick an active profile account framework to delete.")

st.markdown("---")

# Content Display Layout: Left (Live view grid) & Right (Vectors and Historic Engine)
workspace_left, workspace_right = st.columns([7, 5])

with workspace_left:
    st.markdown("### Live View Grid Ledger")
    
    # Load Interactive Grid Ledger Records directly matching searches
    conn = sqlite3.connect(DB_NAME)
    display_query = '''
        SELECT r.id as 'System ID', r.name as 'Rider Identity', MAX(p.payment_date) as 'Most Recent Activity', p.amount as 'Latest Value'
        FROM riders r LEFT JOIN payments p ON r.id = p.rider_id
        WHERE r.name LIKE ?
        GROUP BY r.id ORDER BY r.name ASC
    '''
    df_grid = pd.read_sql_query(display_query, conn, params=(f"%{search_filter}%",))
    conn.close()

    if not df_grid.empty:
        # Safe format logic: converts to float dynamically and catches conversion errors safely
        def safe_currency_format(val):
            try:
                if pd.notnull(val) and val != "None" and val != "":
                    return f"KES {float(val):,.2f}"
            except (ValueError, TypeError):
                pass
            return "None"

        # Safely convert and format columns
        df_grid['Latest Value'] = df_grid['Latest Value'].apply(safe_currency_format)
        df_grid['Most Recent Activity'] = df_grid['Most Recent Activity'].fillna("No activity logged")
        
        st.dataframe(df_grid, use_container_width=True, hide_index=True)
    else:
        st.info("No active logs or matching criteria profiles recorded.")

with workspace_right:
    st.markdown("### 📊 Revenue Log Vectors")
    
    # Quantitative Vector calculation engine logic
    conn = sqlite3.connect(DB_NAME)
    chart_df = pd.read_sql_query('''
        SELECT payment_date as 'Date', SUM(amount) as 'Total' 
        FROM payments GROUP BY payment_date ORDER BY payment_date DESC LIMIT 6
    ''', conn)
    conn.close()
    
    if not chart_df.empty:
        chart_df = chart_df.iloc[::-1]  # Match chronological order
        st.bar_chart(chart_df.set_index('Date'), y='Total', color="#10B981")
    else:
        st.caption("No quantitative metrics tracked dynamically yet.")
        
    st.markdown("### 🔄 Historic Adjustment Engine")
    
    # Historic Table Entry Logs Updates form
    target_history_rider = st.selectbox("Inspect Remittance History Logs", ["Select Rider To Edit"] + all_riders)
    
    if target_history_rider != "Select Rider To Edit":
        conn = sqlite3.connect(DB_NAME)
        history_df = pd.read_sql_query('''
            SELECT p.payment_date as 'Log Date', p.amount as 'Amount (KES)'
            FROM payments p JOIN riders r ON p.rider_id = r.id
            WHERE r.name = ? ORDER BY p.payment_date DESC
        ''', conn, params=(target_history_rider,))
        conn.close()
        
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True, hide_index=True)
            
            # Sub-form fields to handle cell metric rebalancing securely
            with st.form("adjustment_sub_form"):
                target_edit_date = st.selectbox("Select Target Log Date", history_df['Log Date'].tolist())
                new_adjusted_value = st.text_input("Modify Value (KES)")
                submit_adjustment = st.form_submit_button("✏️ Update Balance")
                
                if submit_adjustment:
                    try:
                        clean_new_val = float(new_adjusted_value.strip())
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE payments SET amount = ? 
                            WHERE payment_date = ? AND rider_id = (SELECT id FROM riders WHERE name = ?)
                        ''', (clean_new_val, target_edit_date, target_history_rider))
                        conn.commit()
                        conn.close()
                        st.success("Payment records adjusted securely.")
                        st.rerun()
                    except ValueError:
                        st.error("Amount must be a clean numeric decimal calculation value.")
        else:
            st.info("No timeline logs available for this rider record profile.")
