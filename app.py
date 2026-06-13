import os
import sqlite3
import webbrowser
import pandas as pd
from datetime import datetime
import streamlit as st

# ReportLab Imports for PDF Generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Production Persistent Database Path
DB_DIR = "/data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)
DB_NAME = os.path.join(DB_DIR, "rider_market_system.db")

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

    pdf_path = "/tmp/generated_report.pdf" if os.name != 'nt' else "generated_report.pdf"
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
st.set_page_config(page_title="CeeJay Creations - Dashboard", layout="wide", initial_sidebar_state="expanded")
init_db()

# Custom CSS theme tweaks for a deep dark look
st.markdown("""
    <style>
    .stApp { background-color: #020617; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0B0F19; border-right: 1px solid #1E293B; }
    </style>
""", unsafehtml=True)

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.title("CEEJAY CREATIONS")
    st.subheader("Action Control Core")
    
    # Action 1: Add New Rider
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
            except sqlite3.IntegrityError:
                st.error("Rider profile already exists.")
            finally:
                conn.close()
        else:
            st.warning("Please provide a valid name.")
            
    st.markdown("---")
    
    # Action 2: Record Payment Entries
    st.markdown("### Log Entry Payments")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM riders ORDER BY name ASC")
    all_riders = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    selected_rider = st.selectbox("Select Target Rider", ["Select Rider"] + all_riders)
    log_date = st.date_input("Transaction Date", datetime.today())
    payment_amount = st.text_input("Payment Amount (KES)", placeholder="e.g., 500")
    
    if st.button("💾 Save Entry Log", use_container_width=True):
        if selected_rider == "Select Rider":
            st.error("Please choose a valid active rider account.")
        else:
            try:
                amt_val = float(payment_amount.strip())
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
            except ValueError:
                st.error("Amount must be a valid numeric calculation.")

# --- MAIN WORKSPACE ---
# Header KPIs
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
    st.metric(label="AGGREGATE REVENUE LEDGER", value=f"KES {sum_revenue:,.2f}")

st.markdown("---")

# Filters & Operations Ribbon
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    search_filter = st.text_input("🔍 Filter Live View Identity...")
with col_f2:
    rep_rider = st.selectbox("Notice Targeting", ["All Riders"] + all_riders)
with col_f3:
    rep_date = st.date_input("Notice Filter Start Date", datetime(2026, 1, 1))

# Action Row for Document Engines
col_b1, col_b2, _ = st.columns([2, 2, 4])
with col_b1:
    if st.button("📄 Prepare PDF Notice", use_container_width=True):
        pdf_file, msg = build_pdf_report(rep_date.strftime('%Y-%m-%d'), rep_rider)
        if pdf_file and os.path.exists(pdf_file):
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Notice",
                    data=f,
                    file_name=f"Rider_Notice_{rep_rider}_{rep_date.strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.error(msg)

with col_b2:
    # CSV Export Logic
    conn = sqlite3.connect(DB_NAME)
    query = '''
        SELECT r.name as 'Rider Name', p.payment_date as 'Payment Date', p.amount as 'Amount Received (KES)'
        FROM payments p JOIN riders r ON p.rider_id = r.id 
        ORDER BY r.name ASC, p.payment_date ASC
    '''
    csv_df = pd.read_sql_query(query, conn)
    conn.close()
    
    st.download_button(
        label="📊 Export Spreadsheet CSV",
        data=csv_df.to_csv(index=False).encode('utf-8'),
        file_name="Rider_Market_Ledger.csv",
        mime="text/csv",
        use_container_width=True
    )

st.markdown("### Live View Grid Ledger")

# Load and Render Database Records
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
    st.dataframe(df_grid, use_container_width=True, hide_index=True)
else:
    st.info("No active logs or matching criteria profiles recorded.")