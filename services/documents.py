"""
Document generation service.
"""
import os
import io
import subprocess
from datetime import date, datetime
from typing import Optional, Tuple
from dateutil.relativedelta import relativedelta

import pandas as pd
import openpyxl
import pypdf
from docxtpl import DocxTemplate
from num2words import num2words

from config.settings import settings
from config.constants import MONTHS_RU
from utils.formatters import clean_int_str, safe_int, clean_value


class DocumentService:
    """Service for generating documents from templates."""
    
    LIBREOFFICE_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    
    def __init__(self):
        self.templates_dir = settings.TEMPLATES_DIR
    
    def convert_docx_to_pdf(self, source_docx: str, output_dir: str) -> bool:
        """
        Convert DOCX to PDF using LibreOffice.
        
        Args:
            source_docx: Path to source DOCX file
            output_dir: Directory for output PDF
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(source_docx):
            return False
        
        if not os.path.exists(self.LIBREOFFICE_PATH):
            return False
        
        # Create isolated user profile
        user_profile_dir = os.path.join(output_dir, "LO_User")
        os.makedirs(user_profile_dir, exist_ok=True)
        
        args = [
            self.LIBREOFFICE_PATH,
            f"-env:UserInstallation=file://{user_profile_dir}",
            "--headless",
            "--invisible",
            "--nodefault",
            "--nofirststartwizard",
            "--nolockcheck",
            "--norestore",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            source_docx
        ]
        
        try:
            result = subprocess.run(
                args, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=60
            )
            
            # Check return code for errors
            if result.returncode != 0:
                stderr_msg = result.stderr.decode() if result.stderr else "Unknown error"
                print(f"LibreOffice conversion failed (code {result.returncode}): {stderr_msg}")
                return False
            
            expected_pdf = os.path.join(
                output_dir,
                os.path.splitext(os.path.basename(source_docx))[0] + ".pdf"
            )
            
            return os.path.exists(expected_pdf) and os.path.getsize(expected_pdf) > 0
            
        except subprocess.TimeoutExpired:
            print("LibreOffice conversion timed out")
            return False
        except Exception as e:
            print(f"LibreOffice error: {e}")
            return False
    
    def fill_docx_template(self, template_path: str, context: dict) -> Optional[io.BytesIO]:
        """
        Fill a DOCX template with context data.
        
        Returns:
            BytesIO buffer with filled document or None
        """
        try:
            doc = DocxTemplate(template_path)
            doc.render(context)
            buf = io.BytesIO()
            doc.save(buf)
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"DOCX fill error: {e}")
            return None
    
    def fill_excel_template(self, template_path: str, context: dict) -> Optional[bytes]:
        """
        Fill an Excel template with context data.
        
        Returns:
            Bytes of filled workbook or None
        """
        try:
            wb = openpyxl.load_workbook(template_path)
            
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value and isinstance(cell.value, str) and "{{" in cell.value:
                            val = cell.value
                            for k, v in context.items():
                                # Handle both {{ key }} and {{key}} formats
                                val = val.replace(f"{{{{ {k} }}}}", str(v))
                                val = val.replace(f"{{{{{k}}}}}", str(v))
                            
                            cell.value = val
                            
                            # Try to restore numbers (improved parsing)
                            try:
                                clean = str(val).replace(" ", "").replace(",", ".").strip()
                                if clean and clean not in ["", "-"]:
                                    num = float(clean)
                                    cell.value = int(num) if num.is_integer() else num
                            except (ValueError, TypeError):
                                pass  # Keep as string if not a valid number
            
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return buf.getvalue()
            
        except Exception as e:
            print(f"Excel fill error: {e}")
            return None
    
    def fill_pdf_form(self, template_path: str, data: dict) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Fill a PDF form using pypdf.
        
        Returns:
            Tuple of (filled PDF bytes, error message)
        """
        try:
            reader = pypdf.PdfReader(template_path)
            writer = pypdf.PdfWriter()
            writer.clone_document_from_reader(reader)
            
            # Set NeedAppearances flag to ensure filled fields are visible
            try:
                if "/AcroForm" in writer._root_object:
                    writer._root_object["/AcroForm"].update({
                        pypdf.generic.NameObject("/NeedAppearances"): pypdf.generic.BooleanObject(True)
                    })
            except Exception:
                pass  # Skip if AcroForm not present
            
            clean_data = {k: str(v) for k, v in data.items() if v is not None}
            
            for page in writer.pages:
                writer.update_page_form_field_values(page, clean_data)
            
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)
            return buf.getvalue(), None
            
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def calculate_ndfl_year_to_date(year: int, total_income: float) -> int:
        """Calculate cumulative NDFL for a given year and total income."""
        if year < 2025:
            # Pre-2025 rules: 13% up to 5M, 15% above
            limit_15 = 5_000_000
            if total_income <= limit_15:
                return int(total_income * 0.13)
            else:
                return int(limit_15 * 0.13 + (total_income - limit_15) * 0.15)
        else:
            # 2025+ progressive rules
            # Each tuple is (bracket_width, rate) - NOT cumulative thresholds
            # 0 - 2.4M: 13%
            # 2.4M - 5M: 15% (width = 2.6M)
            # 5M - 20M: 18% (width = 15M)
            # 20M - 50M: 20% (width = 30M)
            # 50M+: 22%
            brackets = [
                (2_400_000, 0.13),   # First 2.4M at 13%
                (2_600_000, 0.15),   # Next 2.6M (2.4M to 5M) at 15%
                (15_000_000, 0.18),  # Next 15M (5M to 20M) at 18%
                (30_000_000, 0.20),  # Next 30M (20M to 50M) at 20%
                (float("inf"), 0.22) # Everything above 50M at 22%
            ]
            
            remaining = total_income
            total_tax = 0.0
            
            for span, rate in brackets:
                if remaining <= 0:
                    break
                taxable = min(remaining, span)
                total_tax += taxable * rate
                remaining -= taxable
            
            return int(total_tax)
    
    @staticmethod
    def get_salary_context(income_str: str) -> dict:
        """Generate context for 12-month salary certificate."""
        try:
            income = int(str(income_str).replace(" ", "")) if income_str else 0
        except:
            income = 0
        
        ctx = {"job_income": f"{income:,}".replace(",", " ")}
        
        today = date.today()
        current_date = today - relativedelta(months=1)
        
        total_income_12 = 0
        total_ndfl_12 = 0
        total_net_12 = 0
        
        for i in range(12):
            m_idx = 12 - i
            loop_date = current_date
            m_name = MONTHS_RU[loop_date.month]
            
            current_month_num = loop_date.month
            cumulative_now = income * current_month_num
            cumulative_prev = income * (current_month_num - 1)
            
            tax_now = DocumentService.calculate_ndfl_year_to_date(loop_date.year, cumulative_now)
            tax_prev = DocumentService.calculate_ndfl_year_to_date(loop_date.year, cumulative_prev)
            
            monthly_ndfl = tax_now - tax_prev
            monthly_net = income - monthly_ndfl
            
            total_income_12 += income
            total_ndfl_12 += monthly_ndfl
            total_net_12 += monthly_net
            
            ctx[f"m_{m_idx}"] = f"{m_name} {loop_date.year}"
            ctx[f"month_{m_idx}"] = m_name
            ctx[f"year_{m_idx}"] = str(loop_date.year)
            ctx[f"ndfl_{m_idx}"] = f"{monthly_ndfl:,}".replace(",", " ")
            ctx[f"net_{m_idx}"] = f"{monthly_net:,}".replace(",", " ")
            ctx[f"income_{m_idx}"] = f"{income:,}".replace(",", " ")
            
            current_date = current_date - relativedelta(months=1)
        
        ctx["job_income_total"] = f"{total_income_12:,}".replace(",", " ")
        ctx["ndfl_total"] = f"{total_ndfl_12:,}".replace(",", " ")
        ctx["net_income_total"] = f"{total_net_12:,}".replace(",", " ")
        ctx["job_income_13"] = ctx["job_income_total"]
        ctx["ndfl_13"] = ctx["ndfl_total"]
        ctx["net_income_13"] = ctx["net_income_total"]
        
        avg_ndfl = int(total_ndfl_12 / 12) if total_ndfl_12 else 0
        ctx["average_ndfl"] = f"{avg_ndfl:,}".replace(",", " ")
        ctx["ndfl"] = ctx["ndfl_12"]
        ctx["net_income"] = ctx["net_12"]
        
        return ctx
    
    def _calculate_age(self, client: dict) -> int:
        """Calculate age from dob if age field is not provided."""
        # Try direct age field first
        age = safe_int(client.get("age", 0))
        if age > 0:
            return age
        
        # Calculate from dob
        dob = client.get("dob")
        if dob:
            try:
                if isinstance(dob, str):
                    dob = pd.to_datetime(dob)
                if hasattr(dob, 'year'):
                    today = date.today()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    return max(0, age)
            except Exception:
                pass
        return 0
    
    def build_document_context(self, client: dict, bank_name: str) -> dict:
        """Build full context dictionary for document generation."""
        from utils.helpers import parse_fio
        
        # Parse FIO
        c_surname = clean_value(client.get("surname"))
        c_name = clean_value(client.get("name"))
        c_patronymic = clean_value(client.get("patronymic"))
        
        if not c_surname and client.get("fio"):
            c_surname, c_name, c_patronymic = parse_fio(client.get("fio"))
        
        # Build object address
        obj_parts = [
            clean_int_str(client.get("obj_index", "")),
            clean_value(client.get("obj_region")),
            clean_value(client.get("obj_city")),
            clean_value(client.get("obj_street")),
            f"д. {clean_int_str(client.get('obj_house'))}" if client.get("obj_house") and str(client.get("obj_house")) != "nan" else "",
            f"корп. {clean_int_str(client.get('obj_korpus'))}" if client.get("obj_korpus") and str(client.get("obj_korpus")) != "nan" else "",
            f"стр. {clean_int_str(client.get('obj_structure'))}" if client.get("obj_structure") and str(client.get("obj_structure")) != "nan" else "",
            f"кв. {clean_int_str(client.get('obj_flat'))}" if client.get("obj_flat") and str(client.get("obj_flat")) != "nan" else "",
        ]
        full_obj_addr = ", ".join([p for p in obj_parts if p and p.strip()])
        
        # Build registration address
        addr_parts = [
            clean_int_str(client.get("addr_index", "")),
            clean_value(client.get("addr_region")),
            clean_value(client.get("addr_city")),
            clean_value(client.get("addr_street")),
            f"д. {clean_int_str(client.get('addr_house'))}" if client.get("addr_house") and str(client.get("addr_house")) != "nan" else "",
            f"корп. {clean_int_str(client.get('addr_korpus'))}" if client.get("addr_korpus") and str(client.get("addr_korpus")) != "nan" else "",
            f"стр. {clean_int_str(client.get('addr_structure'))}" if client.get("addr_structure") and str(client.get("addr_structure")) != "nan" else "",
            f"кв. {clean_int_str(client.get('addr_flat'))}" if client.get("addr_flat") and str(client.get("addr_flat")) != "nan" else "",
        ]
        full_addr_reg = ", ".join([p for p in addr_parts if p and p.strip()])
        
        # Calculate terms
        term_years = safe_int(client.get("loan_term", 0))
        term_months = term_years * 12
        
        # Parse dates safely
        def safe_date_format(val, fmt="%d.%m.%Y"):
            if not val or str(val) in ["nan", "None", ""]:
                return ""
            try:
                return pd.to_datetime(val).strftime(fmt)
            except:
                return ""
        
        context = {
            # Basic info
            "fio": client.get("fio", ""),
            "surname": c_surname,
            "name": c_name,
            "patronymic": c_patronymic,
            "phone": clean_int_str(client.get("phone", "")),
            "email": clean_value(client.get("email")),
            
            # Passport
            "passport_ser": clean_int_str(client.get("passport_ser", "")),
            "passport_num": clean_int_str(client.get("passport_num", "")),
            "passport_issued": clean_value(client.get("passport_issued")),
            "passport_date": safe_date_format(client.get("passport_date")),
            "kpp": clean_value(client.get("kpp")),
            "inn": clean_int_str(client.get("inn", "")),
            "snils": clean_int_str(client.get("snils", "")),
            
            # Personal
            "dob": safe_date_format(client.get("dob")),
            "birth_place": clean_value(client.get("birth_place")),
            "gender": client.get("gender", ""),
            "family_status": client.get("family_status", ""),
            "marriage_contract": clean_value(client.get("marriage_contract")),
            "children_count": clean_int_str(client.get("children_count", "")),
            "children_dates": clean_value(client.get("children_dates")),
            
            # Registration address (parts)
            "addr_index": clean_int_str(client.get("addr_index", "")),
            "addr_region": clean_value(client.get("addr_region")),
            "addr_city": clean_value(client.get("addr_city")),
            "addr_street": clean_value(client.get("addr_street")),
            "addr_house": clean_int_str(client.get("addr_house", "")),
            "addr_korpus": clean_int_str(client.get("addr_korpus", "")),
            "addr_structure": clean_int_str(client.get("addr_structure", "")),
            "addr_flat": clean_int_str(client.get("addr_flat", "")),
            "addr_reg": full_addr_reg,
            
            # Bank and credit
            "bank_name": bank_name,
            "credit_sum": client.get("credit_sum", 0),
            "loan_term": term_years,
            "loan_term_months": term_months,
            "first_pay": safe_int(client.get("first_pay", 0)),
            "obj_price": safe_int(client.get("obj_price", 0)),
            "current_debts": safe_int(client.get("current_debts", 0)),
            "has_coborrower": clean_value(client.get("has_coborrower")),
            "cian_report_link": clean_value(client.get("cian_report_link")),
            
            # Dates
            "today": date.today().strftime("%d.%m.%Y"),
            "today_d": date.today().strftime("%d"),
            "today_m": date.today().strftime("%m"),
            "today_y": date.today().strftime("%Y"),
            
            # Job info
            "job_company": clean_value(client.get("job_company")),
            "job_pos": clean_value(client.get("job_pos")),
            "job_income": clean_int_str(client.get("job_income", "")),
            "job_phone": clean_int_str(client.get("job_phone", "")),
            "job_inn": clean_int_str(client.get("job_inn", "")),
            "job_ceo": clean_value(client.get("job_ceo")),
            "job_address": clean_value(client.get("job_address")),
            "job_sphere": clean_value(client.get("job_sphere")),
            "job_type": clean_value(client.get("job_type")),
            "job_official": clean_value(client.get("job_official")),
            "job_found_date": safe_date_format(client.get("job_found_date")),
            "job_exp": clean_value(client.get("job_exp")),
            "total_exp": clean_int_str(client.get("total_exp", "")),
            "job_start_date": safe_date_format(client.get("job_start_date")),
            "job_start_date_d": safe_date_format(client.get("job_start_date"), "%d"),
            "job_start_date_m": safe_date_format(client.get("job_start_date"), "%m"),
            "job_start_date_y": safe_date_format(client.get("job_start_date"), "%Y"),
            
            # Age (calculate from dob if not provided)
            "age": self._calculate_age(client),
            
            # Object address
            "obj_addr": full_obj_addr,
            "obj_index": clean_int_str(client.get("obj_index", "")),
            "obj_region": clean_value(client.get("obj_region")),
            "obj_city": clean_value(client.get("obj_city")),
            "obj_street": clean_value(client.get("obj_street")),
            "obj_house": clean_int_str(client.get("obj_house", "")),
            "obj_korpus": clean_int_str(client.get("obj_korpus", "")),
            "obj_structure": clean_int_str(client.get("obj_structure", "")),
            "obj_flat": clean_int_str(client.get("obj_flat", "")),
            
            # Object details
            "obj_area": clean_int_str(client.get("obj_area", "")),
            "obj_floor": clean_int_str(client.get("obj_floor", "")),
            "obj_total_floors": clean_int_str(client.get("obj_total_floors", "")),
            "obj_walls": clean_value(client.get("obj_walls")),
            "obj_type": clean_value(client.get("obj_type")),
            "obj_doc_type": clean_value(client.get("obj_doc_type")),
            "obj_date": safe_date_format(client.get("obj_date")),
            "obj_renovation": clean_value(client.get("obj_renovation")),
            
            # Pledge info
            "is_pledged": clean_value(client.get("is_pledged")),
            "pledge_bank": clean_value(client.get("pledge_bank")),
            "pledge_amount": clean_int_str(client.get("pledge_amount", "")),
            
            # Gift (donation) info
            "gift_donor_consent": clean_value(client.get("gift_donor_consent")),
            "gift_donor_registered": clean_value(client.get("gift_donor_registered")),
            "gift_donor_deregister": clean_value(client.get("gift_donor_deregister")),
            
            # Verification comments
            "mosgorsud_comment": clean_value(client.get("mosgorsud_comment")),
            "fssp_comment": clean_value(client.get("fssp_comment")),
            "block_comment": clean_value(client.get("block_comment")),
            
            # Assets
            "assets": clean_value(client.get("assets")),
        }
        
        # Add salary context (12 months)
        salary_ctx = self.get_salary_context(clean_int_str(client.get("job_income", "")))
        context.update(salary_ctx)
        
        # Add income in words
        try:
            income_int = int(clean_int_str(client.get("job_income", 0)))
            context["job_income_propis"] = num2words(income_int, lang="ru")
        except:
            context["job_income_propis"] = ""
        
        # Add 13% NDFL calculations
        try:
            income_int = int(clean_int_str(client.get("job_income", 0)))
            ndfl_13 = int(income_int * 0.13)
            context["ndfl_avg_13"] = f"{ndfl_13:,}".replace(",", " ")
            context["ndfl_total_13_calc"] = f"{ndfl_13 * 12:,}".replace(",", " ")
        except:
            context["ndfl_avg_13"] = ""
            context["ndfl_total_13_calc"] = ""
        
        return context
