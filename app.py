import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz

# Load data from a semicolon-delimited CSV file with error handling
def load_data(file_path):
    try:
        # Use sep=';' for semicolon-delimited CSVs
        df = pd.read_csv(file_path, sep=';', on_bad_lines='skip')  # 'skip' skips bad lines
        return df
    except pd.errors.ParserError as e:
        st.error(f"Error parsing CSV: {e}")
        return None

# Merge stock data with sales data and price data
def merge_data(stock_df, sales_df, price_df):
    # Merge datasets on 'Nama Item'
    merged_df = pd.merge(stock_df, sales_df, on='Nama Item', how='left')
    merged_df = pd.merge(merged_df, price_df, on='Nama Item', how='left', suffixes=('', '_Price'))
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

# Analyze corresponding items based on fuzzy name similarity and price comparison
def find_corresponding_items(df, minus_stock_items, low_sales_items, similarity_threshold=80, price_tolerance=0.1):
    transfer_suggestions = []
    no_suggestions = []

    # Ensure 'Price' columns are numeric
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    low_sales_items['Price'] = pd.to_numeric(low_sales_items['Price'], errors='coerce')
    minus_stock_items['Price'] = pd.to_numeric(minus_stock_items['Price'], errors='coerce')

    for idx, minus_row in minus_stock_items.iterrows():
        minus_item = minus_row['Nama Item']
        minus_stock = minus_row['Stock']
        minus_price = minus_row['Price']
        minus_barcode = minus_row.get('Barcode', '')
        suggestion_found = False  # Flag to check if any suggestion is found

        if pd.isnull(minus_price):
            continue  # Skip if minus item price is not available

        # Fuzzy matching
        possible_matches = process.extract(
            minus_item,
            low_sales_items['Nama Item'],
            scorer=fuzz.partial_ratio,
            limit=None
        )

        # Filter matches based on similarity threshold
        for match_name, match_score, match_idx in possible_matches:
            if match_score >= similarity_threshold:
                related_item = low_sales_items.iloc[match_idx]
                related_item_name = related_item['Nama Item']
                related_item_stock = related_item['Stock']
                related_item_price = related_item['Price']
                related_item_barcode = related_item.get('Barcode', '')

                if pd.isnull(related_item_price) or related_item_stock <= 0:
                    continue  # Skip if price is not available or stock is zero or negative

                # Compare prices within the tolerance
                price_difference = abs(minus_price - related_item_price)
                average_price = (minus_price + related_item_price) / 2
                if average_price == 0:
                    continue  # Avoid division by zero

                price_difference_ratio = price_difference / average_price
                if price_difference_ratio <= price_tolerance:
                    # Suggest transfer
                    total_negative_stock = abs(minus_stock)
                    transfer_amount = min(related_item_stock, total_negative_stock)

                    if transfer_amount > 0:
                        suggestion_found = True  # Set flag to True since we found a suggestion
                        transfer_suggestions.append({
                            'From Item': related_item_name,
                            'From Barcode': related_item_barcode,
                            'To Item': minus_item,
                            'To Barcode': minus_barcode,
                            'Transfer Amount': transfer_amount,
                            'Price Difference (%)': round(price_difference_ratio * 100, 2)
                        })
                        # Update stocks
                        df.loc[df['Nama Item'] == related_item_name, 'Stock'] -= transfer_amount
                        df.loc[df['Nama Item'] == minus_item, 'Stock'] += transfer_amount
                        minus_stock += transfer_amount  # Update minus_stock
                        if minus_stock >= 0:
                            break

        if not suggestion_found:
            # If no suggestion was found for this minus stock item, add it to the list
            no_suggestions.append({
                'Nama Item': minus_item,
                'Barcode': minus_barcode,
                'Stock': minus_stock,
                'Price': minus_price
            })

    transfer_suggestions_df = pd.DataFrame(transfer_suggestions)
    no_suggestions_df = pd.DataFrame(no_suggestions)
    return transfer_suggestions_df, no_suggestions_df

# Streamlit App Interface
st.title('Minus Stock Transfer Suggestion App with Price and Barcode Comparison')
st.write('Upload your stock, sales, and price data to receive stock transfer suggestions based on similar prices and barcodes.')

# File upload interface
stock_file = st.file_uploader('Upload your Stock Data CSV', type='csv')
sales_file = st.file_uploader('Upload your Sales Data CSV', type='csv')
price_file = st.file_uploader('Upload your Price Data CSV', type='csv')

if stock_file and sales_file and price_file:
    stock_data = load_data(stock_file)
    sales_data = load_data(sales_file)
    price_data = load_data(price_file)

    if stock_data is not None and sales_data is not None and price_data is not None:
        merged_data = merge_data(stock_data, sales_data, price_data)
        minus_stock_items = filter_minus_stock(merged_data)
        low_sales_items = filter_low_sales_items(merged_data)
        transfer_suggestions, no_suggestions = find_corresponding_items(merged_data, minus_stock_items, low_sales_items)

        st.write('Suggested Stock Transfers:')
        st.dataframe(transfer_suggestions)

        # Option to download the transfer suggestions as CSV
        if not transfer_suggestions.empty:
            csv = transfer_suggestions.to_csv(index=False)
            st.download_button(label="Download Transfer Suggestions as CSV", data=csv, mime='text/csv')

        # Display minus stock items without suggestions
        st.write('Minus Stock Items without Suggestions:')
        st.dataframe(no_suggestions)

        # Option to download the minus stock items without suggestions as CSV
        if not no_suggestions.empty:
            csv_no_suggestions = no_suggestions.to_csv(index=False)
            st.download_button(label="Download Minus Stock Items without Suggestions as CSV", data=csv_no_suggestions, mime='text/csv')

    else:
        st.error('Error loading one or more files. Please check your CSV files.')
else:
    st.info('Please upload all three CSV files to proceed.')