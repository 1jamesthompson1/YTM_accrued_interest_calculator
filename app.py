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

# Create Gradio app
demo = gr.Interface(
    fn=process_batch_input,
    inputs=gr.File(label="Upload Excel File (.xlsx)"),
    outputs=gr.File(label="Download Processed File"),
    title="YTM accrued interest calculator",
    description="Upload an excel file with bond details to calculate the YTM and accrued interest."
)

# Run the app
if __name__ == "__main__":
    demo.launch()
