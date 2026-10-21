"""
Enhanced report export utilities: CSV, XLSX, and PDF with Spanish formatting.

All exports include:
- Report title and description
- Period and warehouse filters
- Formatted dates and currency (Bolivian format)
- Translated headers and status values
- Grand totals row

XLSX and PDF exports exclude internal ID columns and include the company logo.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image as PdfImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlsxImage
from openpyxl.styles import Alignment, Font, PatternFill, numbers
from openpyxl.utils import get_column_letter


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

LOGO_PATH = Path(__file__).parent.parent / "static" / "logo_receipt.jpg"

COMPANY_NAME = "PARAISO BIKER"

# Columns to exclude from XLSX and PDF exports (internal IDs)
XLSX_PDF_EXCLUDED_COLUMNS = {
    "customer_id", "seller_id", "product_id", "warehouse_id",
    "supplier_id", "category_id"
}


# --------------------------------------------------------------------------- #
# Translations and formatting
# --------------------------------------------------------------------------- #

STATUS_TRANSLATIONS = {
    "completed": "Completada",
    "pending": "Pendiente",
    "cancelled": "Cancelada",
    "received": "Recibida",
    "active": "Activo",
    "inactive": "Inactivo",
}

PAYMENT_TRANSLATIONS = {
    "efectivo": "Efectivo",
    "transferencia": "Transferencia",
    "tarjeta": "Tarjeta",
}

BOOLEAN_TRANSLATIONS = {
    True: "Sí",
    False: "No",
}

# Status colors for PDF (RGB format)
STATUS_COLORS = {
    "completed": "16A34A",
    "pending": "D97706",
    "cancelled": "DC2626",
    "received": "2563EB",
}

# Header translations per report type
HEADER_TRANSLATIONS = {
    "sales": {
        "sale_id": "N° Venta",
        "sale_date": "Fecha",
        "customer_id": "ID Cliente",
        "customer_name": "Cliente",
        "seller_id": "ID Vendedor",
        "seller_name": "Vendedor",
        "payment_method": "Método Pago",
        "status": "Estado",
        "items_count": "Items",
        "units_sold": "Unidades",
        "subtotal": "Subtotal",
        "tax_amount": "IVA",
        "total_amount": "Total",
        "warehouse_name": "Sucursal",
    },
    "purchases": {
        "order_id": "N° Orden",
        "order_date": "Fecha",
        "supplier_id": "ID Proveedor",
        "supplier_name": "Proveedor",
        "warehouse_id": "ID Sucursal",
        "warehouse_name": "Sucursal",
        "status": "Estado",
        "items_count": "Items",
        "units_ordered": "Unidades",
        "total_amount": "Total",
    },
    "inventory": {
        "product_id": "ID Producto",
        "name": "Producto",
        "sku": "SKU",
        "category_id": "ID Categoría",
        "category_name": "Categoría",
        "warehouse_id": "ID Sucursal",
        "warehouse_name": "Sucursal",
        "quantity": "Cantidad",
        "reserved_quantity": "Reservado",
        "min_stock_level": "Stock Mínimo",
        "max_stock_level": "Stock Máximo",
        "unit_price": "Precio Unitario",
        "stock_value": "Valor Stock",
        "unit_cost": "Costo Unitario",
        "stock_value_at_cost": "Valor Costo",
        "is_low_stock": "Stock Bajo",
        "is_out_of_stock": "Agotado",
    },
    "customers": {
        "customer_id": "ID Cliente",
        "name": "Nombre",
        "email": "Email",
        "phone": "Teléfono",
        "is_active": "Activo",
        "loyalty_tier": "Nivel",
        "loyalty_points": "Puntos",
        "orders": "Ordenes",
        "total_spent": "Total Gastado",
        "last_sale_date": "Última Compra",
    },
    "products": {
        "product_id": "ID Producto",
        "name": "Producto",
        "sku": "SKU",
        "category_id": "ID Categoría",
        "category_name": "Categoría",
        "unit_price": "Precio",
        "is_active": "Activo",
        "units_sold": "Unidades Vendidas",
        "revenue": "Ingresos",
        "stock_quantity": "Stock",
    },
    "profit": {
        "product_id": "ID Producto",
        "name": "Producto",
        "sku": "SKU",
        "units_sold": "Unidades Vendidas",
        "revenue": "Ingresos",
        "cogs": "Costo",
        "gross_profit": "Ganancia Bruta",
        "margin_pct": "Margen %",
    },
    "profit-summary": {
        "period_label": "Periodo",
        "revenue": "Ingresos",
        "cogs": "Costo",
        "gross_profit": "Ganancia Bruta",
        "margin_pct": "Margen %",
        "sales_count": "N° Ventas",
    },
    "abc": {
        "product_id": "ID Producto",
        "name": "Producto",
        "sku": "SKU",
        "revenue": "Ingresos",
        "revenue_pct": "% Ingresos",
        "cumulative_pct": "% Acumulado",
        "abc_class": "Clase ABC",
        "units_sold": "Unidades Vendidas",
    },
    "slow-moving": {
        "product_id": "ID Producto",
        "name": "Producto",
        "sku": "SKU",
        "category_name": "Categoría",
        "warehouse_name": "Sucursal",
        "quantity": "Stock",
        "last_sale_date": "Última Venta",
        "days_since_last_sale": "Días sin Venta",
        "stock_value": "Valor Stock",
    },
    "sellers": {
        "seller_id": "ID Vendedor",
        "seller_name": "Vendedor",
        "role_name": "Rol",
        "sales_count": "Ventas",
        "units_sold": "Unidades",
        "revenue": "Ingresos",
        "avg_ticket": "Ticket Promedio",
        "tax_collected": "IVA Cobrado",
    },
}

# Numeric columns that need currency formatting per report type
CURRENCY_COLUMNS = {
    "sales": ["subtotal", "tax_amount", "total_amount"],
    "purchases": ["total_amount"],
    "inventory": ["unit_price", "stock_value", "unit_cost", "stock_value_at_cost"],
    "customers": ["total_spent"],
    "products": ["unit_price", "revenue"],
    "profit": ["revenue", "cogs", "gross_profit"],
    "profit-summary": ["revenue", "cogs", "gross_profit"],
    "abc": ["revenue"],
    "sellers": ["revenue", "avg_ticket", "tax_collected"],
}

# Columns that should be summed for totals
TOTAL_COLUMNS = {
    "sales": ["units_sold", "subtotal", "tax_amount", "total_amount"],
    "purchases": ["units_ordered", "total_amount"],
    "inventory": ["quantity", "reserved_quantity"],
    "customers": ["orders", "total_spent", "loyalty_points"],
    "products": ["units_sold", "revenue", "stock_quantity"],
    "profit": ["units_sold", "revenue", "cogs", "gross_profit"],
    "profit-summary": ["revenue", "cogs", "gross_profit"],
    "abc": ["revenue"],
    "sellers": ["sales_count", "units_sold", "revenue", "avg_ticket", "tax_collected"],
}


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

def filter_headers(headers: Sequence[str]) -> List[str]:
    """Filter out internal ID columns for XLSX and PDF exports."""
    return [h for h in headers if h not in XLSX_PDF_EXCLUDED_COLUMNS]


def format_date_es(value: Any) -> str:
    """Format date/datetime to DD/MM/YYYY."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return value
    return str(value)


def format_datetime_es(value: Any) -> str:
    """Format datetime to DD/MM/YYYY HH:mm."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value
    return str(value)


def format_currency_es(value: Any) -> str:
    """Format number to Bolivian currency format: 1.230,50"""
    if value is None:
        return ""
    try:
        num = float(value)
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)


def format_number_es(value: Any) -> str:
    """Format number with thousands separator."""
    if value is None:
        return ""
    try:
        num = float(value)
        if num == int(num):
            return f"{int(num):,}".replace(",", ".")
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)


def translate_value(value: Any, field_name: str = "") -> str:
    """Translate status, payment method, and boolean values."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return BOOLEAN_TRANSLATIONS.get(value, str(value))
    if field_name == "status":
        return STATUS_TRANSLATIONS.get(str(value), str(value))
    if field_name == "payment_method":
        return PAYMENT_TRANSLATIONS.get(str(value), str(value))
    return str(value)


def format_cell_value(value: Any, field_name: str, report_type: str) -> str:
    """Format a cell value based on its type and field name."""
    if value is None:
        return ""

    # Date fields
    if field_name in ("sale_date", "order_date", "last_sale_date"):
        return format_datetime_es(value)
    if "date" in field_name:
        return format_date_es(value)

    # Currency fields
    if report_type in CURRENCY_COLUMNS and field_name in CURRENCY_COLUMNS[report_type]:
        return format_currency_es(value)

    # Status and payment method translations
    if field_name in ("status", "payment_method"):
        return translate_value(value, field_name)

    # Boolean fields
    if isinstance(value, bool):
        return translate_value(value)

    # Numeric fields
    if isinstance(value, (int, float, Decimal)):
        return format_number_es(value)

    return str(value)


def get_translated_headers(headers: Sequence[str], report_type: str) -> List[str]:
    """Get Spanish translated headers for a report type."""
    translations = HEADER_TRANSLATIONS.get(report_type, {})
    return [translations.get(h, h) for h in headers]


def get_report_description(
    report_type: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_names: Optional[List[str]] = None,
) -> List[str]:
    """Generate report description lines."""
    report_titles = {
        "sales": "Reporte de Ventas",
        "purchases": "Reporte de Compras",
        "inventory": "Reporte de Inventario",
        "customers": "Reporte de Clientes",
        "products": "Reporte de Productos",
        "profit": "Reporte de Rentabilidad",
        "profit-summary": "Resumen de Ganancia",
        "abc": "Análisis ABC",
        "slow-moving": "Productos de Movimiento Lento",
        "sellers": "Reporte de Vendedores",
    }

    title = report_titles.get(report_type, "Reporte")
    lines = [title]

    if from_date and to_date:
        lines.append(f"Periodo: {format_date_es(from_date)} - {format_date_es(to_date)}")
    elif from_date:
        lines.append(f"Desde: {format_date_es(from_date)}")
    elif to_date:
        lines.append(f"Hasta: {format_date_es(to_date)}")

    if warehouse_names:
        if len(warehouse_names) == 1:
            lines.append(f"Sucursal: {warehouse_names[0]}")
        else:
            lines.append(f"Sucursales: {', '.join(warehouse_names)}")
    else:
        lines.append("Sucursales: Todas las sucursales")

    lines.append(f"Generado: {format_date_es(datetime.now())}")

    return lines


def calculate_totals(
    rows: List[Dict[str, Any]], 
    headers: Sequence[str], 
    report_type: str
) -> Optional[Dict[str, Any]]:
    """Calculate totals for numeric columns."""
    if report_type not in TOTAL_COLUMNS:
        return None

    total_columns = TOTAL_COLUMNS[report_type]
    totals: Dict[str, Any] = {h: "" for h in headers}

    for col in total_columns:
        if col in headers:
            total_sum = sum(
                float(row.get(col, 0) or 0)
                for row in rows
            )
            totals[col] = total_sum

    totals[headers[0]] = ""
    if len(headers) > 1:
        totals[headers[1]] = ""
    if len(headers) > 2:
        totals[headers[2]] = "TOTALES:"

    return totals


# --------------------------------------------------------------------------- #
# CSV Export
# --------------------------------------------------------------------------- #

def rows_to_csv_response_enhanced(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    filename: str = "report.csv",
    report_type: str = "sales",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_names: Optional[List[str]] = None,
) -> StreamingResponse:
    """Enhanced CSV export with Spanish formatting, description, and totals."""
    buffer = io.StringIO()

    # Write BOM for Excel compatibility
    buffer.write("\ufeff")

    # Write description
    description_lines = get_report_description(report_type, from_date, to_date, warehouse_names)
    buffer.write(COMPANY_NAME + "\n")
    for line in description_lines:
        buffer.write(line + "\n")
    buffer.write("\n")

    # Write headers
    translated_headers = get_translated_headers(headers, report_type)
    writer = csv.writer(buffer)
    writer.writerow(translated_headers)

    # Write data rows
    for row in rows:
        writer.writerow([
            format_cell_value(row.get(h), h, report_type)
            for h in headers
        ])

    # Write totals
    totals = calculate_totals(list(rows), headers, report_type)
    if totals:
        buffer.write("\n")
        writer.writerow([
            format_cell_value(totals.get(h), h, report_type) if totals.get(h) != "TOTALES:" else "TOTALES:"
            for h in headers
        ])

    buffer.seek(0)

    def _iter():
        chunk = buffer.read(8192)
        while chunk:
            yield chunk.encode("utf-8")
            chunk = buffer.read(8192)

    return StreamingResponse(
        _iter(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# XLSX Export
# --------------------------------------------------------------------------- #

BRAND_COLOR = "D15700"

# Styling constants
HEADER_BG_COLOR = "F5F5F5"
HEADER_FONT_COLOR = "374151"
ROW_ALT_COLOR = "FAFAFA"
TOTALS_BG_COLOR = "F0F0F0"
BORDER_COLOR = "E5E7EB"

HEADER_FONT_STYLE = Font(name="Helvetica", size=9, bold=True, color=HEADER_FONT_COLOR)
DATA_FONT_STYLE = Font(name="Helvetica", size=9, color=HEADER_FONT_COLOR)
TOTALS_FONT_STYLE = Font(name="Helvetica", size=9, bold=True, color=HEADER_FONT_COLOR)
TITLE_FONT_STYLE = Font(name="Helvetica", size=11, bold=True, color="1F2937")
DESC_FONT_STYLE = Font(name="Helvetica", size=9, italic=True, color="6B7280")

HEADER_FILL = PatternFill(start_color=HEADER_BG_COLOR, end_color=HEADER_BG_COLOR, fill_type="solid")
ALT_ROW_FILL = PatternFill(start_color=ROW_ALT_COLOR, end_color=ROW_ALT_COLOR, fill_type="solid")
TOTALS_FILL = PatternFill(start_color=TOTALS_BG_COLOR, end_color=TOTALS_BG_COLOR, fill_type="solid")


def _prepare_xlsx_data(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    report_type: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Prepare filtered data for XLSX export."""
    filtered_headers = filter_headers(headers)
    filtered_rows = [
        {h: row.get(h) for h in filtered_headers}
        for row in rows
    ]
    return filtered_headers, filtered_rows


def rows_to_xlsx_response(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    filename: str = "report.xlsx",
    report_type: str = "sales",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_names: Optional[List[str]] = None,
) -> StreamingResponse:
    """Export report as formatted Excel workbook."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"

    # Prepare filtered data (exclude ID columns)
    filtered_headers, filtered_rows = _prepare_xlsx_data(rows, headers, report_type)

    # Row 1-2: Logo at top-left
    if LOGO_PATH.exists():
        logo = XlsxImage(str(LOGO_PATH))
        logo.width = 200
        logo.height = 65
        ws.add_image(logo, "A1")

    # Row 4-7: Description below logo
    description_lines = get_report_description(report_type, from_date, to_date, warehouse_names)
    for i, line in enumerate(description_lines, start=5):
        cell = ws.cell(row=i, column=1, value=line)
        if i == 5:
            cell.font = TITLE_FONT_STYLE
        else:
            cell.font = DESC_FONT_STYLE

    # Row 9: Column headers (after blank row 8)
    start_row = 9
    translated_headers = get_translated_headers(filtered_headers, report_type)
    for col_idx, header in enumerate(translated_headers, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=header)
        cell.font = HEADER_FONT_STYLE
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = _create_border(bottom=BORDER_COLOR)

    # Write data rows
    data_start_row = start_row + 1
    for row_idx, row in enumerate(filtered_rows, start=data_start_row):
        for col_idx, header in enumerate(filtered_headers, start=1):
            value = row.get(header)
            cell = ws.cell(row=row_idx, column=col_idx)

            # Format value
            if header in ("sale_date", "order_date", "last_sale_date"):
                if isinstance(value, str):
                    try:
                        cell.value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        cell.value = value
                else:
                    cell.value = value
                cell.number_format = "DD/MM/YYYY HH:MM"
            elif report_type in CURRENCY_COLUMNS and header in CURRENCY_COLUMNS[report_type]:
                cell.value = float(value) if value else 0
                cell.number_format = '#,##0.00'
            elif header == "status":
                cell.value = translate_value(value, header)
                # Color status (aRGB format for openpyxl)
                if value and str(value) in STATUS_COLORS:
                    cell.font = Font(name="Helvetica", size=9, color=f"FF{STATUS_COLORS[str(value)]}")
                else:
                    cell.font = DATA_FONT_STYLE
                cell.alignment = Alignment(horizontal="center")
                row_is_alt = (row_idx - data_start_row) % 2 == 1
                if row_is_alt:
                    cell.fill = ALT_ROW_FILL
                continue  # Skip the default font assignment
            elif header == "payment_method":
                cell.value = translate_value(value, header)
            elif isinstance(value, bool):
                cell.value = translate_value(value)
            else:
                cell.value = value
                cell.font = DATA_FONT_STYLE

            # Alternating row colors
            row_is_alt = (row_idx - data_start_row) % 2 == 1
            if row_is_alt:
                cell.fill = ALT_ROW_FILL

            cell.alignment = Alignment(vertical="center")

    # Write totals
    totals = calculate_totals(filtered_rows, filtered_headers, report_type)
    if totals:
        totals_row = data_start_row + len(filtered_rows) + 1
        for col_idx, header in enumerate(filtered_headers, start=1):
            cell = ws.cell(row=totals_row, column=col_idx)
            value = totals.get(header)

            if value == "TOTALES:":
                cell.value = "TOTALES:"
                cell.font = TOTALS_FONT_STYLE
                cell.fill = TOTALS_FILL
                cell.alignment = Alignment(horizontal="right")
            elif value and report_type in CURRENCY_COLUMNS and header in CURRENCY_COLUMNS[report_type]:
                cell.value = float(value)
                cell.number_format = '#,##0.00'
                cell.font = TOTALS_FONT_STYLE
                cell.fill = TOTALS_FILL
            elif value:
                cell.value = value
                cell.font = TOTALS_FONT_STYLE
                cell.fill = TOTALS_FILL
            else:
                cell.fill = TOTALS_FILL

    # Auto-width columns
    for col_idx in range(1, len(filtered_headers) + 1):
        max_length = 0
        col_letter = get_column_letter(col_idx)
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, min_row=data_start_row):
            for cell in row:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_length + 2, 40)

    # Freeze header row
    ws.freeze_panes = f"A{data_start_row}"

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    content = buffer.getvalue()

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _create_border(bottom: str = BORDER_COLOR):
    """Create a subtle bottom border."""
    from openpyxl.styles import Border, Side
    return Border(bottom=Side(style="thin", color=bottom))


# --------------------------------------------------------------------------- #
# PDF Export
# --------------------------------------------------------------------------- #

def _prepare_pdf_data(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    report_type: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Prepare filtered data for PDF export."""
    filtered_headers = filter_headers(headers)
    filtered_rows = [
        {h: row.get(h) for h in filtered_headers}
        for row in rows
    ]
    return filtered_headers, filtered_rows


def _format_pdf_cell(value: Any, field_name: str, report_type: str) -> Tuple[str, Optional[str]]:
    """Format a cell value for PDF, returning (text, color)."""
    if field_name == "status":
        text = translate_value(value, field_name)
        color = STATUS_COLORS.get(str(value)) if value else None
        if color:
            color = f"#{color}"
        return text, color
    
    text = format_cell_value(value, field_name, report_type)
    return text, None


def rows_to_pdf_response(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    filename: str = "report.pdf",
    report_type: str = "sales",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    warehouse_names: Optional[List[str]] = None,
) -> StreamingResponse:
    """Export report as formatted PDF."""
    buffer = io.BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12*mm,
        leftMargin=12*mm,
        topMargin=12*mm,
        bottomMargin=12*mm,
    )

    # Build content
    content = []

    # Logo at top-left
    if LOGO_PATH.exists():
        logo = PdfImage(str(LOGO_PATH), width=200, height=65)
        logo_table = Table([[logo]], colWidths=[200])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        content.append(logo_table)
        content.append(Spacer(1, 8))

    # Description below logo
    report_titles = {
        "sales": "Reporte de Ventas",
        "purchases": "Reporte de Compras",
        "inventory": "Reporte de Inventario",
        "customers": "Reporte de Clientes",
        "products": "Reporte de Productos",
        "profit": "Reporte de Rentabilidad",
        "profit-summary": "Resumen de Ganancia",
        "abc": "Análisis ABC",
        "slow-moving": "Productos de Movimiento Lento",
        "sellers": "Reporte de Vendedores",
    }

    title_style = ParagraphStyle(
        'ReportTitle',
        fontSize=12,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )
    desc_style = ParagraphStyle(
        'ReportDesc',
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=2,
    )

    title = report_titles.get(report_type, "Reporte")
    content.append(Paragraph(title, title_style))

    description_lines = get_report_description(report_type, from_date, to_date, warehouse_names)
    for line in description_lines[1:]:  # Skip title, already added
        content.append(Paragraph(line, desc_style))

    content.append(Spacer(1, 10))

    # Prepare filtered data (exclude ID columns)
    filtered_headers, filtered_rows = _prepare_pdf_data(rows, headers, report_type)

    # Build table data
    translated_headers = get_translated_headers(filtered_headers, report_type)
    table_data = [translated_headers]

    for row in filtered_rows:
        table_row = []
        for header in filtered_headers:
            value = row.get(header)
            text, color = _format_pdf_cell(value, header, report_type)
            table_row.append(text)
        table_data.append(table_row)

    # Add totals row
    totals = calculate_totals(filtered_rows, filtered_headers, report_type)
    if totals:
        totals_row = []
        for header in filtered_headers:
            value = totals.get(header)
            if value == "TOTALES:":
                totals_row.append("TOTALES:")
            elif value:
                text, _ = _format_pdf_cell(value, header, report_type)
                totals_row.append(text)
            else:
                totals_row.append("")
        table_data.append(totals_row)

    # Calculate column widths (proportional, sum = 1.0)
    # Use landscape A4 width (297mm), not portrait (210mm)
    available_width = landscape(A4)[0] - 24*mm  # landscape width minus 12mm margins each side

    # Assign proportional widths based on content type
    col_widths = []
    for header in filtered_headers:
        if header in ("sale_id", "order_id"):
            col_widths.append(available_width * 0.05)
        elif header in ("sale_date", "order_date", "last_sale_date"):
            col_widths.append(available_width * 0.10)
        elif header == "customer_name":
            col_widths.append(available_width * 0.14)
        elif header == "seller_name":
            col_widths.append(available_width * 0.14)
        elif header in ("warehouse_name", "category_name", "role_name", "supplier_name"):
            col_widths.append(available_width * 0.07)
        elif header in ("payment_method", "status", "is_active", "is_low_stock", "is_out_of_stock", "abc_class"):
            col_widths.append(available_width * 0.08)
        elif header in ("units_sold", "units_ordered", "quantity", "reserved_quantity", "items_count"):
            col_widths.append(available_width * 0.05)
        elif header in ("subtotal", "tax_amount", "total_amount", "unit_price", "stock_value",
                        "unit_cost", "stock_value_at_cost", "total_spent", "revenue", "cogs",
                        "gross_profit", "avg_ticket", "tax_collected"):
            col_widths.append(available_width * 0.08)
        elif header in ("margin_pct", "cumulative_pct"):
            col_widths.append(available_width * 0.05)
        else:
            col_widths.append(available_width * 0.08)

    # Create table
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Table style
    table_style = [
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{HEADER_BG_COLOR}")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(f"#{HEADER_FONT_COLOR}")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    ]

    # Horizontal borders only (no vertical grid)
    table_style.append(('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor(f"#{BORDER_COLOR}")))
    table_style.append(('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor(f"#{BORDER_COLOR}")))

    # Alternating row colors
    for i in range(1, len(table_data) - (1 if totals else 0)):
        if i % 2 == 0:
            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(f"#{ROW_ALT_COLOR}")))

    # Totals row style
    if totals:
        totals_row_idx = len(table_data) - 1
        table_style.append(('BACKGROUND', (0, totals_row_idx), (-1, totals_row_idx), colors.HexColor(f"#{TOTALS_BG_COLOR}")))
        table_style.append(('FONTNAME', (0, totals_row_idx), (-1, totals_row_idx), 'Helvetica-Bold'))
        table_style.append(('LINEABOVE', (0, totals_row_idx), (-1, totals_row_idx), 1, colors.HexColor("#D1D5DB")))
        table_style.append(('ALIGN', (0, totals_row_idx), (-2, totals_row_idx), 'RIGHT'))

    table.setStyle(TableStyle(table_style))
    content.append(table)

    # Build PDF
    doc.build(content)
    buffer.seek(0)
    pdf_content = buffer.getvalue()

    return StreamingResponse(
        iter([pdf_content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Keep original function for backwards compatibility
def rows_to_csv_response(
    rows: Sequence[Dict[str, Any]],
    headers: Sequence[str],
    filename: str = "report.csv",
) -> StreamingResponse:
    """Legacy CSV export (no formatting)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    buffer.seek(0)

    def _iter():
        chunk = buffer.read(8192)
        while chunk:
            yield chunk.encode("utf-8")
            chunk = buffer.read(8192)

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
