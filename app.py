import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz


# Load stock data from a semicolon-delimited CSV file with error handling
def load_data(file_path):
    try:
        # Use sep=';' for semicolon-delimited CSVs
        df = pd.read_csv(file_path, sep=';', on_bad_lines='skip')  # 'skip' skips bad lines
        return df
    except pd.errors.ParserError as e:
        print(f"Error parsing CSV: {e}")
        return None


# Merge stock data with sales data
def merge_data(stock_df, sales_df):
    # Merge datasets on 'Item Name' or 'Item ID'
    merged_df = pd.merge(stock_df, sales_df, on='Nama Item', how='left')
    return merged_df


# Filter minus stock items
def filter_minus_stock(df):
    minus_stock_items = df[df['Stock'] < 0]
    return minus_stock_items


# Filter items that have low or no sales
def filter_low_sales_items(df, low_sales_threshold=5):
    df['Total Sales'] = pd.to_numeric(df['Total Sales'], errors='coerce').fillna(0)
    low_sales_items = df[df['Total Sales'] <= low_sales_threshold]
    return low_sales_items


# Analyze corresponding items based on fuzzy name similarity
def find_corresponding_items(df, minus_stock_items, low_sales_items, similarity_threshold=80):
    transfer_suggestions = []

    for minus_item, minus_stock in zip(minus_stock_items['Nama Item'], minus_stock_items['Stock']):
        possible_matches = process.extract(minus_item, low_sales_items['Nama Item'], scorer=fuzz.partial_ratio,
                                           limit=None)
        related_items = [match[0] for match in possible_matches if match[1] >= similarity_threshold]
        related_items_df = low_sales_items[
            low_sales_items['Nama Item'].isin(related_items) & (low_sales_items['Stock'] > 0)]

        if not related_items_df.empty:
            total_negative_stock = abs(minus_stock)
            for _, related_item in related_items_df.iterrows():
                item_name = related_item['Nama Item']
                available_stock = related_item['Stock']
                transfer_amount = min(available_stock, total_negative_stock)

                if transfer_amount > 0:
                    transfer_suggestions.append({
                        'From Item': item_name,
                        'To Item': minus_item,
                        'Transfer Amount': transfer_amount
                    })
                    df.loc[df['Nama Item'] == item_name, 'Stock'] -= transfer_amount
                    total_negative_stock -= transfer_amount
                    if total_negative_stock <= 0:
                        break
    return pd.DataFrame(transfer_suggestions)


# Streamlit App Interface
st.title('Minus Stock Transfer Suggestion App')
st.write('Upload your stock and sales data, and receive stock transfer suggestions.')

# File upload interface
stock_file = st.file_uploader('Upload your Stock Data CSV', type='csv')
sales_file = st.file_uploader('Upload your Sales Data CSV', type='csv')

if stock_file and sales_file:
    stock_data = load_data(stock_file)
    sales_data = load_data(sales_file)

    if stock_data is not None and sales_data is not None:
        merged_data = merge_data(stock_data, sales_data)
        minus_stock_items = filter_minus_stock(merged_data)
        low_sales_items = filter_low_sales_items(merged_data)
        transfer_suggestions = find_corresponding_items(merged_data, minus_stock_items, low_sales_items)

        st.write('Suggested Stock Transfers:')
        st.dataframe(transfer_suggestions)

        # Option to download the results as CSV
        if not transfer_suggestions.empty:
            csv = transfer_suggestions.to_csv(index=False)
            st.download_button(label="Download Transfer Suggestions as CSV", data=csv, mime='text/csv')