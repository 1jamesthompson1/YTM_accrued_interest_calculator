import pandas as pd
import scipy.optimize as opt
from datetime import datetime

def calculate_coupon_payment_amount(face_value, coupon_rate, coupon_frequency):
    '''
    Calculates the fixed coupon payment amount for a bond
    Takes the yearly return and divides it by the number of payments per year
    '''
    return face_value * coupon_rate / coupon_frequency

def generate_payment_dates(start_date, maturity_date, coupon_frequency):
    '''
    Takes in the start date, maturity date, and coupon frequency and returns a list of payment dates
    Assumes:  
    1. the payment dates will always be on the same day of month as the first payment
    2. the maturity date is the last payment date
    3. the payment dates are equally spaced
    '''
    dates = pd.date_range(start=start_date, end=maturity_date, freq=f"{12//coupon_frequency}M", )
    # Set it to be the same day of the month as the first coupon date
    dates = list(dates.map(lambda x: x.replace(day=start_date.day) if start_date.day <= x.days_in_month else x))

    maturity_date = pd.Timestamp(maturity_date)
    if maturity_date not in dates:
        dates.append(maturity_date)

    return dates

def populate_cashflows(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    '''
    Takes in the bond details and returns a DataFrame of cashflows with payment dates and elapsed days
    '''
    cashflows = list()

    payment_amount = calculate_coupon_payment_amount(face_value, coupon_rate, coupon_frequency)

    # Payments will be on the same date of the month as the first coupon date. Separated by a fixed number of months.
    payment_dates = generate_payment_dates(first_coupon_date, maturity_date, coupon_frequency)
    cashflow_dates = [pd.Timestamp(settlement_date)] + payment_dates

    for index, payment_date in enumerate(cashflow_dates):
        elapsed_days = (payment_date - cashflows[-1]["Date"]).days if index > 0 else 0
        if index == 0:
            cashflows.append({'Date': payment_date, 'Cash Flow': -purchase_price, 'Elapsed Days': elapsed_days})
        elif index == 1:
            if first_coupon_amount != 0:
                cashflows.append({'Date': payment_date, 'Cash Flow': first_coupon_amount, 'Elapsed Days': elapsed_days})
        elif index == len(cashflow_dates) - 1:
            cashflows.append({'Date': payment_date, 'Cash Flow': face_value + payment_amount, 'Elapsed Days': elapsed_days})
            break
        else:
            cashflows.append({'Date': payment_date, 'Cash Flow': payment_amount, 'Elapsed Days': elapsed_days})

        # Add in end of tax year if needed
        if index < len(cashflow_dates) - 1:
            next_end_of_tax_year = pd.Timestamp(f"{payment_date.year}-03-31") if payment_date < pd.Timestamp(f"{payment_date.year}-03-31") else pd.Timestamp(f"{payment_date.year + 1}-03-31")
            if next_end_of_tax_year < cashflow_dates[index+1]:
                cashflows.append({
                    'Date': next_end_of_tax_year,
                    'Cash Flow': 0,
                    'Elapsed Days': (next_end_of_tax_year - payment_date).days
                })

    next_end_of_tax_year = pd.Timestamp(f"{payment_dates[-1].year}-03-31") if payment_dates[-1].month < 3 else pd.Timestamp(f"{payment_dates[-1].year + 1}-03-31")
    cashflows.append({
        'Date': next_end_of_tax_year,
        'Cash Flow': 0,
        'Elapsed Days': (next_end_of_tax_year - payment_dates[-1]).days
    })

    return pd.DataFrame(cashflows).fillna(0)

def calc_daily_rate(ytm, frequency):
    true_rate = (1 + ytm/frequency) ** frequency - 1
    daily_rate = (1 + true_rate) ** (1 / 365) - 1

    return daily_rate

def PV_of_cashflow(ytm, cashflows, frequency):
    daily_rate = calc_daily_rate(ytm, frequency)
    PV_factor = cashflows.apply(lambda x: (1 + daily_rate) ** (-(x['Date'] - cashflows.loc[0, 'Date']).days), axis=1)
    PV_of_cashflows = cashflows['Cash Flow'] * PV_factor
    return PV_of_cashflows.sum()

def calculate_ytm(cashflows, first_guess, frequency):

    ytm = opt.fsolve(PV_of_cashflow, first_guess, (cashflows, frequency), xtol=1e-12)

    return ytm[0]

def populate_interest_principle_columns(cashflows, daily_rate):
    new_columns = list()

    for index, row in cashflows.iterrows():
        if index == 0:
            new_columns.append({
                "CurrentInterest": 0,
                "CurrentPrincipal": cashflows.loc[index, 'Cash Flow'],
                "CumulativeInterest": 0,
                "ClosingPrincipal": cashflows.loc[index, 'Cash Flow']
            })
            continue
        current_interest = ((1+daily_rate)**cashflows.loc[index, 'Elapsed Days'] - 1) * (-new_columns[- 1]['ClosingPrincipal'])
        current_principal = cashflows.loc[index, 'Cash Flow'] - current_interest
        new_columns.append({
            "CurrentInterest": current_interest,
            "CurrentPrincipal": current_principal,
            "CumulativeInterest": new_columns[-1]['CumulativeInterest'] + current_interest,
            "ClosingPrincipal": new_columns[-1]['ClosingPrincipal'] + current_principal
        })

    return cashflows.join(pd.DataFrame(new_columns))

def interest_to_balance_data(df):
    for index, row in df.iterrows():
        if not (row["Date"].month == 3 and row["Date"].day == 31): # Check if it is the end of a tax year
            df.loc[index, 'InterestToBalance'] = 0
            continue
        
        df.loc[index, 'InterestToBalance'] = df.loc[index, 'CumulativeInterest'] - df.loc[0:(index-1), 'InterestToBalance'].sum()

    return df

def tax_to_declare(df, face_value):
    '''
    Add next to the interest to balance the amount of extra tax that needs to be declared. This is worked out with InterestToBalance - sum(cashflows from tax year)
    '''
    df['TaxableInterest'] = float(0)
    for index, row in df.iterrows():
        if row['InterestToBalance'] != 0:
            df.loc[index, 'TaxableInterest'] = row['InterestToBalance'] - df.loc[1:(index-1), 'Cash Flow'].sum() - df.loc[1:(index-1), 'TaxableInterest'].sum() + df.loc[1:(index-1), 'InterestToBalance'].sum() + (face_value if index == len(df)-1 else 0)

    return df


def complete_calculation(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    cashflows = populate_cashflows(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)

    ytm = calculate_ytm(cashflows, coupon_rate, coupon_frequency)

    daily_rate = calc_daily_rate(ytm, coupon_frequency)

    cashflows_with_interest_principal = populate_interest_principle_columns(cashflows, daily_rate)

    cashflows_with_interest_balance = interest_to_balance_data(cashflows_with_interest_principal)

    add_taxable_interest = tax_to_declare(cashflows_with_interest_balance, face_value)

    return {
        "df": add_taxable_interest,
        "ytm": ytm,
        "daily_rate": daily_rate
    }

def validate_inputs(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    
    if purchase_price <= 0:
        return "Purchase price must be greater than 0"

    if face_value <= 0:
        return "Face value must be greater than 0"

    if coupon_rate <= 0 and coupon_rate >= 1:
        return "Coupon rate must be greater than 0 and less than 1"

    if coupon_frequency not in [1,2,4,6,12]:
        return "Coupon frequency must be one of 1, 2, 4, 6, or 12"

    if first_coupon_amount < 0:
        return "First coupon amount cannot be negative"

    try:
        if settlement_date is pd.NaT:
            return "Settlement date is malformed"
        if first_coupon_date is pd.NaT:
            return "First coupon date is malformed"
        if maturity_date is pd.NaT:
            return "Maturity date is malformed"

        # Validate chronological order of dates
        if settlement_date > first_coupon_date:
            return "Settlement date must be before first coupon date"
        if first_coupon_date > maturity_date:
            return "First coupon date must be before maturity date"

    except Exception as e:
        return f"Date validation error: {e}"

    return None