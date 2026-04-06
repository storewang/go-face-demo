import pandas as pd
from typing import List
from io import BytesIO

from app.models import AttendanceLog


class ExportService:
    @staticmethod
    def export_attendance_to_excel(
        records: List[AttendanceLog], start_date: str = None, end_date: str = None
    ) -> BytesIO:
        data = []
        for record in records:
            data.append(
                {
                    "记录ID": record.id,
                    "工号": record.employee_id or "",
                    "姓名": record.name or "",
                    "类型": "上班" if record.action_type == "CHECK_IN" else "下班",
                    "置信度": f"{record.confidence:.2f}" if record.confidence else "",
                    "结果": "成功" if record.result == "SUCCESS" else "失败",
                    "时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if record.created_at
                    else "",
                }
            )

        df = pd.DataFrame(data)
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="考勤记录", index=False)

            worksheet = writer.sheets["考勤记录"]
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
                col_letter = (
                    chr(65 + idx)
                    if idx < 26
                    else chr(64 + idx // 26) + chr(65 + idx % 26)
                )
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)

        output.seek(0)
        return output

    @staticmethod
    def export_attendance_summary(
        records: List[AttendanceLog], start_date: str, end_date: str
    ) -> BytesIO:
        summary = {}
        for record in records:
            key = record.employee_id or "未知"
            if key not in summary:
                summary[key] = {
                    "工号": key,
                    "姓名": record.name or "未知",
                    "上班次数": 0,
                    "下班次数": 0,
                    "成功次数": 0,
                    "失败次数": 0,
                }

            if record.action_type == "CHECK_IN":
                summary[key]["上班次数"] += 1
            else:
                summary[key]["下班次数"] += 1

            if record.result == "SUCCESS":
                summary[key]["成功次数"] += 1
            else:
                summary[key]["失败次数"] += 1

        df = pd.DataFrame(list(summary.values()))
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="考勤汇总", index=False)

        output.seek(0)
        return output


export_service = ExportService()
