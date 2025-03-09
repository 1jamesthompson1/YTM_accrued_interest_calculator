import gradio as gr
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

import calculator

variable_descriptions = """
**PurchasePrice**: The price at which the bond was purchased.  
**FaceValue**: The face value of the bond.  
**CouponRate**: The annual coupon rate of the bond.  
**CouponFrequency**: The number of coupon payments per year (The calculator is setup to accept 1, 2, 4, 6, or 12).  
**FirstCouponAmount**: The amount of the first coupon payment (This needed because sometimes the first coupon payment is missed so its 0, or the first coupon payment is smaller than the expected amount due to it not being a full cycle.).   
**SettlementDate**: The date the bond was purchased.  
**FirstCouponDate**: The date of the first coupon payment (It may be zero).  
**MaturityDate**: The date the bond matures.  
"""
def create_template():
    # Create an empty dataframe with the necessary columns
    template_df = pd.DataFrame(columns=[
        "BondCode", "PurchaseAmount", "FaceValue", "CouponRate", "CouponFrequency",
        "FirstCouponAmount", "SettlementDate", "FirstCouponDate", "MaturityDate"
    ])
    
    # Save to Excel as a template
    output_path = "bond_template.xlsx"
    template_df.to_excel(output_path, index=False)
    
    return output_path  # Return the path to the template file

# Create Gradio app for batch processing
batch_description = f"""
### Instructions for Batch Processing:
1. Upload an Excel file with the bond details (e.g., Purchase Amount, Face Value, Coupon Rate, etc.).
2. Ensure that each row represents a different bond.
3. The app will validate the inputs and check for errors (e.g., missing or incorrect values).
4. Once validated, the app will calculate the YTM and accrued interest for each bond and generate a processed Excel file.
5. You will be able to download the processed file with the results.  

Instructions for the different inputs:  
{variable_descriptions}
"""

# Create Gradio app for single processing
single_description = f"""
### Instructions for Single Bond Calculation:
1. Enter the details of a single bond in the form fields (e.g., Purchase Price, Face Value, Coupon Rate, etc.).
2. Ensure that all fields are correctly filled to avoid validation errors.
3. The app will calculate the YTM (Yield to Maturity) and accrued interest based on the provided information.
4. The results will be displayed in a table format, along with the YTM and daily rate.  

Instructions for the different inputs:  
{variable_descriptions}
"""
def process_batch_input(file):
    # Read the uploaded Excel file
    df = pd.read_excel(file.name)

    problems = list()
    for index, row in df.iterrows():
        error = calculator.validate_inputs(row["PurchaseAmount"], row["FaceValue"], row["CouponRate"], row["CouponFrequency"], row["FirstCouponAmount"], row["SettlementDate"], row["FirstCouponDate"], row["MaturityDate"])
        if error:
            problems.append(f"Row {index}({row['BondCode']}): {error}")

    if len(problems) > 0:
        raise ValueError("There are problems with the input:\n\n" + "\n".join(problems))

    results = [calculator.complete_calculation(row["PurchaseAmount"], row["FaceValue"], row["CouponRate"], row["CouponFrequency"], row["FirstCouponAmount"], row["SettlementDate"], row["FirstCouponDate"], row["MaturityDate"]) for index, row in df.iterrows()]

    output_path = f"{file.name.split('.')[0]}_processed_{datetime.now(tz=ZoneInfo('Pacific/Auckland')).strftime('%Y-%m-%d|%H:%M:%S')}.xlsx"

    with pd.ExcelWriter(output_path) as writer:
        for (index, row), result in zip(df.iterrows(), results):
            code = row["BondCode"]
            summary_df = pd.DataFrame({
                "BondCode": [code],
                "PurchaseAmount": [row["PurchaseAmount"]],
                "FaceValue": [row["FaceValue"]],
                "CouponRate": [row["CouponRate"]],
                "CouponFrequency": [row["CouponFrequency"]],
                "FirstCouponAmount": [row["FirstCouponAmount"]],
                "SettlementDate": [row["SettlementDate"].strftime('%d/%m/%Y')],
                "FirstCouponDate": [row["FirstCouponDate"].strftime('%d/%m/%Y')],
                "MaturityDate": [row["MaturityDate"].strftime('%d/%m/%Y')],
                "calculated YTM": [result["ytm"]],
                "calculated DailyRate": [result["daily_rate"]]
            })

            number_of_rows = len(result['df'])

            formulas_df = pd.DataFrame({
                "BondCode": "",
                "PurchaseAmount": f"=sum(B5:B{number_of_rows+5})",
                "ElapsedDays": "",
                "CurrentInterest": f"=sum(D5:D{number_of_rows+5})",
                "CurrentPrincipal": f"=sum(E5:E{number_of_rows+5})",
                "CumulativeInterest": f"=F{number_of_rows+4}",
                "ClosingPrincipal": f"=G{number_of_rows+4}",
                "InterestToBalance": f"=sum(H5:H{number_of_rows+5})"
            }, index=[0])

            # Clean result date to just be date string
            result['df']['Date'] = pd.to_datetime(result['df']['Date']).dt.strftime('%d/%m/%Y')

            # Make all other columns calcluated to 2 dp
            result['df']['ClosingPrincipal'] = result['df']['ClosingPrincipal'].apply(lambda x: round(x, 2))
            result['df']['InterestToBalance'] = result['df']['InterestToBalance'].apply(lambda x: round(x, 2))
            
            summary_df.to_excel(writer, sheet_name=code, index=False)
            result['df'].to_excel(writer, sheet_name=code, index=False, startrow=3)
            formulas_df.to_excel(writer, sheet_name=code, index=False, header=False, startrow=number_of_rows+5)
    return output_path  # Returning file path for download

def process_single_input(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    error = calculator.validate_inputs(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)
    if error:
        raise ValueError("There are problems with the input:\n\n" + error)

    result = calculator.complete_calculation(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)
    return result["df"], result["ytm"], result["daily_rate"]  # Returning the DataFrame for display

# Create Gradio app
batch_processing = gr.Interface(
    fn=process_batch_input,
    inputs=gr.File(label="Upload Excel File (.xlsx)"),
    outputs=gr.File(label="Download Processed File"),
    description=batch_description
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
    description=single_description
)

# Add a new interface for downloading the template
template_interface = gr.Interface(
    fn=create_template,
    inputs=[],
    outputs=gr.File(label="Download Template (.xlsx)"),
    description="Click the button below to download the Excel template for entering bond details.",
)

demo = gr.TabbedInterface(
    [batch_processing, single_processing, template_interface],
    ["Batch Processing", "Single Processing", "Download Template"],
    title="YTM accrued interest calculator",
)
# Run the app
if __name__ == "__main__":
    demo.launch()
