"""Utility helpers: PDF generation, audit logging, file handling."""
import os
import uuid
from datetime import datetime
from flask import current_app, request
from models import db, AuditLog


def allowed_image(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_IMAGE_EXTENSIONS']


def allowed_doc(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_DOC_EXTENSIONS']


def save_upload(file, subfolder='vehicles'):
    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
    file.save(dest)
    return filename


def log_action(user_id, action, module, record_id=None, details=None):
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            record_id=record_id,
            details=details,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        pass


def generate_quote_number(doc_type, settings):
    from models import Quotation
    prefix_map = {
        'quotation': settings.quote_prefix or 'SLE-QT',
        'proforma_invoice': settings.pi_prefix or 'SLE-PI',
        'tax_invoice': settings.invoice_prefix or 'SLE-INV',
    }
    prefix = prefix_map.get(doc_type, 'SLE-DOC')
    year = datetime.utcnow().year
    count = Quotation.query.filter(
        Quotation.quote_no.like(f"{prefix}-{year}-%")
    ).count()
    return f"{prefix}-{year}-{str(count + 1).zfill(4)}"


def generate_sale_ref():
    from models import Sale
    year = datetime.utcnow().year
    count = Sale.query.filter(Sale.sale_ref.like(f"SLE-SALE-{year}-%")).count()
    return f"SLE-SALE-{year}-{str(count + 1).zfill(4)}"


# ─── PDF Generation ────────────────────────────────────────────────────────────
def generate_quotation_pdf(quotation):
    """Generate a PDF for a quotation/invoice and return bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=18*mm, rightMargin=18*mm)

    styles = getSampleStyleSheet()
    accent = colors.HexColor('#1a3a5c')
    light_gray = colors.HexColor('#f5f5f5')
    mid_gray = colors.HexColor('#cccccc')

    body_style = ParagraphStyle('body', fontSize=9, leading=13)
    h1 = ParagraphStyle('h1', fontSize=18, textColor=accent, spaceAfter=2, fontName='Helvetica-Bold')
    h2 = ParagraphStyle('h2', fontSize=10, textColor=accent, fontName='Helvetica-Bold')
    right = ParagraphStyle('right', fontSize=9, alignment=TA_RIGHT)
    center = ParagraphStyle('center', fontSize=9, alignment=TA_CENTER)
    small = ParagraphStyle('small', fontSize=8, textColor=colors.gray)

    settings = quotation.customer  # we'll grab settings separately
    from models import SystemSettings
    s = SystemSettings.query.first()

    company_name = s.company_name if s else 'Sonnac Lanka Enterprises'
    company_addr = s.company_address if s else 'Negombo, Sri Lanka'
    company_phone = s.company_phone if s else ''
    company_email = s.company_email if s else ''

    story = []

    # Header
    header_data = [
        [Paragraph(f'<b>{company_name}</b>', ParagraphStyle('ch', fontSize=16, textColor=accent, fontName='Helvetica-Bold')),
         Paragraph(f'<b>{quotation.doc_type_label.upper()}</b>', ParagraphStyle('dt', fontSize=20, textColor=accent, alignment=TA_RIGHT, fontName='Helvetica-Bold'))],
        [Paragraph(f'{company_addr}<br/>{company_phone}<br/>{company_email}', small),
         Paragraph(f'<b>No:</b> {quotation.quote_no}<br/><b>Date:</b> {quotation.created_at.strftime("%d %b %Y")}<br/><b>Valid Until:</b> {quotation.valid_until.strftime("%d %b %Y") if quotation.valid_until else "—"}', ParagraphStyle('ri', fontSize=9, alignment=TA_RIGHT))],
    ]
    header_table = Table(header_data, colWidths=[95*mm, 80*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, mid_gray),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5*mm))

    # Bill To
    cust = quotation.customer
    bill_to = f'<b>Bill To:</b><br/>{cust.name}<br/>'
    if cust.nic_passport:
        bill_to += f'NIC/Passport: {cust.nic_passport}<br/>'
    if cust.phone:
        bill_to += f'Tel: {cust.phone}<br/>'
    if cust.address:
        bill_to += cust.address

    bt_data = [[Paragraph(bill_to, body_style), '']]
    bt_table = Table(bt_data, colWidths=[95*mm, 80*mm])
    bt_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), light_gray),
                                   ('PADDING', (0, 0), (-1, -1), 8)]))
    story.append(bt_table)
    story.append(Spacer(1, 5*mm))

    # Vehicle info if linked
    if quotation.vehicle:
        v = quotation.vehicle
        veh_text = f'<b>Vehicle:</b> {v.year} {v.make} {v.model}'
        if v.chassis_no:
            veh_text += f' | Chassis: {v.chassis_no}'
        story.append(Paragraph(veh_text, body_style))
        story.append(Spacer(1, 3*mm))

    # Items table
    item_data = [['#', 'Description', 'Qty', 'Unit Price (LKR)', 'Total (LKR)']]
    for i, item in enumerate(quotation.items, 1):
        item_data.append([
            str(i), item.description, f'{item.quantity:.0f}',
            f'{item.unit_price:,.2f}', f'{item.total:,.2f}'
        ])

    items_table = Table(item_data, colWidths=[8*mm, 85*mm, 15*mm, 35*mm, 32*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_gray]),
        ('GRID', (0, 0), (-1, -1), 0.3, mid_gray),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 3*mm))

    # Totals
    discount = quotation.discount_amount or (quotation.subtotal * (quotation.discount_pct or 0) / 100)
    totals_data = []
    totals_data.append(['', 'Subtotal:', f'LKR {quotation.subtotal:,.2f}'])
    if discount:
        totals_data.append(['', 'Discount:', f'- LKR {discount:,.2f}'])
    if quotation.tax_amount:
        totals_data.append(['', f'Tax ({quotation.tax_rate}%):', f'LKR {quotation.tax_amount:,.2f}'])
    totals_data.append(['', Paragraph('<b>TOTAL</b>', ParagraphStyle('tot', fontName='Helvetica-Bold', fontSize=11)), Paragraph(f'<b>LKR {quotation.total:,.2f}</b>', ParagraphStyle('totr', fontName='Helvetica-Bold', fontSize=11, alignment=TA_RIGHT))])

    tot_table = Table(totals_data, colWidths=[95*mm, 45*mm, 35*mm])
    tot_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LINEABOVE', (1, -1), (2, -1), 1, accent),
        ('LINEBELOW', (1, -1), (2, -1), 1, accent),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(tot_table)

    # Notes & Terms
    if quotation.notes:
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph('<b>Notes:</b>', h2))
        story.append(Paragraph(quotation.notes, body_style))

    if quotation.payment_terms:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('<b>Payment Terms:</b>', h2))
        story.append(Paragraph(quotation.payment_terms, body_style))

    if s and s.bank_details:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('<b>Bank Details:</b>', h2))
        story.append(Paragraph(s.bank_details, body_style))

    # Signature
    story.append(Spacer(1, 12*mm))
    sig_data = [
        [Paragraph('_____________________', center), Paragraph('_____________________', center)],
        [Paragraph('Authorized Signature', center), Paragraph('Customer Signature', center)],
        [Paragraph(company_name, center), Paragraph(cust.name, center)],
    ]
    sig_table = Table(sig_data, colWidths=[87*mm, 87*mm])
    sig_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 0), (-1, -1), 9)]))
    story.append(sig_table)

    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=mid_gray))
    story.append(Paragraph(f'Generated by {company_name} Vehicle Management System', ParagraphStyle('footer', fontSize=7, textColor=colors.gray, alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_cost_sheet_pdf(vehicle, cost_sheet):
    """Generate cost sheet PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=18*mm, rightMargin=18*mm)

    from models import SystemSettings
    s = SystemSettings.query.first()
    accent = colors.HexColor('#1a3a5c')
    light_gray = colors.HexColor('#f5f5f5')
    mid_gray = colors.HexColor('#cccccc')

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', fontSize=16, textColor=accent, fontName='Helvetica-Bold', spaceAfter=4)
    body = ParagraphStyle('body', fontSize=9, leading=13)
    right = ParagraphStyle('right', fontSize=9, alignment=TA_RIGHT)
    bold9 = ParagraphStyle('bold9', fontSize=9, fontName='Helvetica-Bold')

    story = []
    company_name = s.company_name if s else 'Sonnac Lanka Enterprises'

    story.append(Paragraph(company_name, h1))
    story.append(Paragraph(f'<b>VEHICLE COST SHEET</b>', ParagraphStyle('sub', fontSize=13, textColor=accent)))
    story.append(Spacer(1, 5*mm))

    veh_info = [
        ['Vehicle', f'{vehicle.year} {vehicle.make} {vehicle.model}'],
        ['Chassis No', vehicle.chassis_no or '—'],
        ['Engine No', vehicle.engine_no or '—'],
        ['Date', cost_sheet.updated_at.strftime('%d %b %Y') if cost_sheet.updated_at else '—'],
    ]
    veh_table = Table(veh_info, colWidths=[50*mm, 125*mm])
    veh_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (0, -1), light_gray),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.3, mid_gray),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(veh_table)
    story.append(Spacer(1, 5*mm))

    purchase_lkr = (cost_sheet.purchase_price_fc or 0) * (cost_sheet.exchange_rate or 1)

    rows = [
        ['COST ITEM', 'AMOUNT (LKR)', ''],
        [f'Purchase Price ({cost_sheet.currency or "USD"} {cost_sheet.purchase_price_fc or 0:,.2f} × {cost_sheet.exchange_rate or 0:,.2f})', f'{purchase_lkr:,.2f}', ''],
        ['LC Value', f'{(cost_sheet.lc_value or 0):,.2f}', ''],
        ['Bank Charges', f'{(cost_sheet.bank_charges or 0):,.2f}', ''],
        ['LC Interest', f'{(cost_sheet.lc_interest or 0):,.2f}', ''],
        ['Import Duty', f'{(cost_sheet.import_duty or 0):,.2f}', ''],
        ['Customs Levy', f'{(cost_sheet.customs_levy or 0):,.2f}', ''],
        ['Excise Duty', f'{(cost_sheet.excise_duty or 0):,.2f}', ''],
        ['VAT on Import', f'{(cost_sheet.vat_import or 0):,.2f}', ''],
        ['Port Handling', f'{(cost_sheet.port_handling or 0):,.2f}', ''],
        ['Freight', f'{(cost_sheet.freight or 0):,.2f}', ''],
        ['Insurance (Import)', f'{(cost_sheet.insurance_import or 0):,.2f}', ''],
        ['Agent Fees', f'{(cost_sheet.agent_fees or 0):,.2f}', ''],
        ['Clearing Charges', f'{(cost_sheet.clearing_charges or 0):,.2f}', ''],
        ['Inland Transport', f'{(cost_sheet.inland_transport or 0):,.2f}', ''],
        [f'Other Costs{" - " + cost_sheet.other_costs_note if cost_sheet.other_costs_note else ""}', f'{(cost_sheet.other_costs or 0):,.2f}', ''],
        [Paragraph('<b>TOTAL LANDED COST</b>', bold9), Paragraph(f'<b>LKR {cost_sheet.total_landed_cost:,.2f}</b>', ParagraphStyle('br', fontSize=9, alignment=TA_RIGHT, fontName='Helvetica-Bold')), ''],
        [f'Target Margin ({cost_sheet.target_margin_pct or 0}%)', '', ''],
        [Paragraph('<b>TARGET SELLING PRICE</b>', bold9), Paragraph(f'<b>LKR {cost_sheet.target_selling_price:,.2f}</b>', ParagraphStyle('br2', fontSize=9, alignment=TA_RIGHT, fontName='Helvetica-Bold')), ''],
    ]

    cost_table = Table(rows, colWidths=[100*mm, 55*mm, 20*mm])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_gray]),
        ('GRID', (0, 0), (-1, -1), 0.3, mid_gray),
        ('LINEABOVE', (0, -3), (-1, -3), 1, accent),
        ('LINEABOVE', (0, -1), (-1, -1), 1, accent),
        ('LINEBELOW', (0, -1), (-1, -1), 1, accent),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(cost_table)

    if cost_sheet.notes:
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph('<b>Notes:</b>', bold9))
        story.append(Paragraph(cost_sheet.notes, body))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(f'Generated: {datetime.utcnow().strftime("%d %b %Y %H:%M")} | {company_name}',
                            ParagraphStyle('footer', fontSize=7, textColor=colors.gray, alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
