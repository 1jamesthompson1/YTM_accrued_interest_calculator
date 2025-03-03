import gradio as gr
import pandas as pd
from datetime import datetime

import calculator

def process_batch_input(file):
    # Read the uploaded Excel file
    df = pd.read_excel(file.name)

    problems = list()
    for index, row in df.iterrows():
        error = calculator.validate_inputs(row["PurchaseAmount"], row["FaceValue"], row["CouponRate"], row["CouponFrequency"], row["FirstCouponAmount"], row["SettlementDate"], row["FirstCouponDate"], row["MaturityDate"])
        if error:
            problems.append(f"Row {index}: {error}")

    if len(problems) > 0:
        raise ValueError("There are problems with the input:\n\n" + "\n".join(problems))

    results = [calculator.complete_calculation(row["PurchaseAmount"], row["FaceValue"], row["CouponRate"], row["CouponFrequency"], row["FirstCouponAmount"], row["SettlementDate"], row["FirstCouponDate"], row["MaturityDate"]) for index, row in df.iterrows()]

    output_path = f"{file.name.split('.')[0]}_processed_{datetime.now().strftime('%Y-%m-%d|%H:%M:%S')}.xlsx"

    with pd.ExcelWriter(output_path) as writer:
        for bond, result in zip(df["BondCode"], results):
            result['df'].to_excel(writer, sheet_name=bond, index=False)

    return output_path  # Returning file path for download

def process_single_input(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    error = calculator.validate_inputs(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)
    if error:
        raise ValueError("There are problems with the input:\n\n" + error)

    result = calculator.complete_calculation(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)
    print(result['df'])
    return result["df"], result["ytm"], result["daily_rate"]  # Returning the DataFrame for display

# Create Gradio app
batch_processing = gr.Interface(
    fn=process_batch_input,
    inputs=gr.File(label="Upload Excel File (.xlsx)"),
    outputs=gr.File(label="Download Processed File"),
    title="YTM accrued interest calculator",
    description="Upload an excel file with bond details to calculate the YTM and accrued interest."
)

single_processing = gr.Interface(
    fn=process_single_input,
    inputs=[
        gr.Number(label="Purchase Price"),
        gr.Number(label="Face Value"),
        gr.Number(label="Coupon Rate"),
        gr.Number(label="Coupon Frequency"),
        gr.Number(label="First Coupon Amount"),
        gr.DateTime(label="Settlement Date", include_time=False, type="datetime"),
        gr.DateTime(label="First Coupon Date", include_time=False, type="datetime"),
        gr.DateTime(label="Maturity Date", include_time=False, type="datetime")
    ],
    outputs=[
        gr.DataFrame(label="Results"),
        gr.Number(label="YTM"),
        gr.Number(label="Daily Rate")
    ],
    title="YTM accrued interest calculator",
    description="Enter bond details to calculate the YTM and accrued interest."
)

demo = gr.TabbedInterface(
    [batch_processing, single_processing],
    ["Batch Processing", "Single Processing"],
    title="YTM accrued interest calculator",
)
# Run the app
if __name__ == "__main__":
    demo.launch()
