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
    dates = pd.date_range(start=start_date, end=maturity_date, freq=f"{12//coupon_frequency}ME", )
    dates = list(dates.map(lambda x: x.replace(day=pd.to_datetime(start_date).day)))

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
        if row['Cash Flow'] != 0:
            df.loc[index, 'InterestToBalance'] = 0
            continue
        
        df.loc[index, 'InterestToBalance'] = df.loc[index, 'CumulativeInterest'] - df.loc[0:(index-1), 'InterestToBalance'].sum()

    return df

def complete_calculation(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    cashflows = populate_cashflows(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date)

    ytm = calculate_ytm(cashflows, coupon_rate, coupon_frequency)

    daily_rate = calc_daily_rate(ytm, coupon_frequency)

    cashflows_with_interest_principal = populate_interest_principle_columns(cashflows, daily_rate)

    cashflows_with_interest_balance = interest_to_balance_data(cashflows_with_interest_principal)

    return {
        "df": cashflows_with_interest_balance,
        "ytm": ytm,
        "daily_rate": daily_rate
    }

def validate_inputs(purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date):
    if not all([purchase_price, face_value, coupon_rate, coupon_frequency, first_coupon_amount, settlement_date, first_coupon_date, maturity_date]):
        return "All fields are required"
    

    return None