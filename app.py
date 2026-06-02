import streamlit as st
from pathlib import Path
import tempfile
import uuid

from layout_generator import generate_final_pdf


st.set_page_config(
    page_title="标签自动排版系统",
    layout="wide"
)

st.title("标签自动排版系统")

st.write("上传主标、地址标、洗水标 PDF，系统会自动生成横版 A4 排版 PDF。")

main_pdf = st.file_uploader("上传主标 PDF", type=["pdf"])
addr_pdf = st.file_uploader("上传地址标 PDF", type=["pdf"])
wash_pdf = st.file_uploader("上传洗水标 PDF", type=["pdf"])

if st.button("生成排版 PDF"):
    if not main_pdf or not addr_pdf or not wash_pdf:
        st.error("请先上传三个 PDF 文件。")
    else:
        with st.spinner("正在生成，请稍等..."):
            job_id = str(uuid.uuid4())[:8]

            temp_dir = Path(tempfile.mkdtemp())

            main_path = temp_dir / f"{job_id}_main.pdf"
            addr_path = temp_dir / f"{job_id}_addr.pdf"
            wash_path = temp_dir / f"{job_id}_wash.pdf"

            output_pdf = temp_dir / f"{job_id}_layout.pdf"
            preview_png = temp_dir / f"{job_id}_preview.png"

            main_path.write_bytes(main_pdf.read())
            addr_path.write_bytes(addr_pdf.read())
            wash_path.write_bytes(wash_pdf.read())

            generate_final_pdf(
                str(main_path),
                str(addr_path),
                str(wash_path),
                str(output_pdf),
                str(preview_png)
            )

            st.success("生成完成")

            st.subheader("排版预览")
            st.image(str(preview_png), use_container_width=True)

            with open(output_pdf, "rb") as f:
                st.download_button(
                    label="下载 PDF",
                    data=f,
                    file_name="final_label_layout.pdf",
                    mime="application/pdf"
                )
