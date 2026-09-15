import collections
import datetime
import os

import pandas as pd
import plotly.express as px
import numpy as np

# Load the spreadsheet with pandas
df = pd.read_excel("teardown notes.ods")

# Remove extraneous columns
df = df[["Company", "Device", "Apprx Release", "Microcontroller", "BLE chip"]]

# Discard rows without "Apprx Release"
df = df.dropna(subset=['Apprx Release'])

# Replace "See microcontroller", "?", and "-" with blank in "Microcontroller" and "BLE chip" columns
for column_name in ["Microcontroller", "BLE chip"]:
    df[column_name] = df[column_name].replace(['See microcontroller', 'See microcontroller?', '?', '-'], np.nan)

# Discard rows where both "Microcontroller" and "BLE chip" are blank
df = df.dropna(subset=['Microcontroller', 'BLE chip'], how='all')


def get_label(row):
    # Make a label that is the Company + Device name unless the device name is (or starts with) the company name
    if row['Device'].startswith(row['Company']):
        return row['Device']
    return row['Company'] + ' ' + row['Device']


# Make a list of important companies to note later
important_companies = ["Abbott", "Alivecor", "Amazon", "Apple", "Baxter / Bardy Dx",
                       "Boston Scientific / Preventice", "Dexcom", "Fitbit", "Garmin", "Google",
                       "Masimo", "Medtronic", "Samsung", "Vitalconnect", "Whoop"]
# Remove duplicates and sort
important_companies = sorted(list(set(important_companies)))
suggested_companies = sorted(
    ((company, count) for company, count in collections.Counter(list(df["Company"])).items()
     if count > 3 and company not in important_companies),
    key=lambda item: item[0]
)
if suggested_companies:
    print("Companies with more than 3 products not on the important company list:")
    for company, count in suggested_companies:
        print(f"  {company} ({count})")

important_companies = sorted(important_companies)

# Create "Brand and Microcontroller" column, and make copies of rows that have multiple chips
rows_to_append = pd.DataFrame()
for index, row in df.iterrows():
    if pd.isna(row['BLE chip']) and not pd.isna(row['Microcontroller']):
        df.at[index, 'Brand and Microcontroller'] = row['Microcontroller']
    elif pd.isna(row['Microcontroller']) and not pd.isna(row['BLE chip']):
        df.at[index, 'Brand and Microcontroller'] = row['BLE chip']
    elif not pd.isna(row['Microcontroller']) and not pd.isna(row['BLE chip']):
        df.at[index, 'Brand and Microcontroller'] = row['Microcontroller']
        df.at[index, 'Device'] += '*'  # Add asterisk to Device
        copy_row = row.copy()
        copy_row['Brand and Microcontroller'] = row['BLE chip']
        copy_row['Device'] += '*'
        rows_to_append = pd.concat([rows_to_append, pd.DataFrame([copy_row])], ignore_index=True)

df = pd.concat([df, rows_to_append], ignore_index=True)

df['Company and Device'] = df.apply(get_label, axis=1)

df['Company'] = df['Company'].apply(lambda x: x if x in important_companies else 'Other')

# Put "Other" at the end
important_companies = important_companies + ["Other"]

# Remove "BLE chip" and "Microcontroller" columns
df = df.drop(columns=['BLE chip', 'Microcontroller'])

# Make a new "Microcontroller Brand" column
df['Microcontroller Brand'] = df['Brand and Microcontroller'].str.split().str[0]


# Map each category in 'Microcontroller Brand' to a numerical value
def number_of_rows_matching_micro(microcontroller_brand):
    return df[df["Microcontroller Brand"] == microcontroller_brand].shape[0]


sorted_microcontroller_brands = sorted(df['Microcontroller Brand'].unique(), key=number_of_rows_matching_micro)
microcontroller_mapping = {brand: i for i, brand in enumerate(sorted_microcontroller_brands)}
df['Microcontroller Value'] = df['Microcontroller Brand'].map(microcontroller_mapping)


# Function to generate bee swarm x positions
def beeswarm_positions(df, x_col, y_col, max_row_length, x_dist, y_dist):
    df = df.copy()
    df[x_col + ' Beeswarm'] = df[x_col].astype(float)
    df[y_col + ' Beeswarm'] = df[y_col].astype(float)

    grouped = df.groupby([x_col, y_col])

    for (x_val, y_val), group in grouped:
        n_points = len(group)
        n_rows = (n_points - 1) // max_row_length + 1

        for i, (index, row) in enumerate(group.iterrows()):
            row_num = i // max_row_length
            col_num = i % max_row_length

            if row_num == n_rows - 1:
                actual_row_length = n_points - (n_rows - 1) * max_row_length
                x_beeswarm = x_val + (col_num - (actual_row_length - 1) / 2) * x_dist
            else:
                x_beeswarm = x_val + (col_num - (max_row_length - 1) / 2) * x_dist

            y_beeswarm = y_val + (row_num - (n_rows - 1) / 2) * y_dist

            df.at[index, x_col + ' Beeswarm'] = x_beeswarm
            df.at[index, y_col + ' Beeswarm'] = y_beeswarm

    return df


# Apply beeswarm positioning to Approx Release
df = beeswarm_positions(df, x_col='Apprx Release', y_col='Microcontroller Value',
                        max_row_length=4, x_dist=0.2, y_dist=0.3)

df['Label'] = df['Company and Device'] + '<br>' + \
              df['Brand and Microcontroller'] + '<br>' + \
              '~' + df['Apprx Release'].astype(int).astype(str)

color_map = {'Other': 'black'}

fig = px.scatter(
    df,
    x='Apprx Release Beeswarm',
    y='Microcontroller Value Beeswarm',
    hover_data={'Apprx Release Beeswarm': False, 'Microcontroller Value Beeswarm': False, 'Label': True},
    title="Microcontrollers and BLE Chips Used by Various IoT or Wearable Products, by Year",
    color='Company',
    color_discrete_map=color_map,
    category_orders={'Company': important_companies}
)

fig.update_traces(hovertemplate="%{customdata[0]}")

y_tick_values = list(microcontroller_mapping.values())
y_tick_text = list(microcontroller_mapping.keys())

fig.add_annotation(
    showarrow=False,
    text="*Product has multiple<br>microcontrollers and/or BLE chips.<br><br>Plot generated " + datetime.date.today().strftime("%d %b %Y").lstrip("0"),
    font=dict(size=10),
    xref='paper',
    x=1.01,
    xanchor="left",
    yref='paper',
    y=-0.02,
    yanchor="top",
    align='left'
)

# Update layout for better appearance
fig.update_layout(
    width=1030,
    height=920,
    xaxis=dict(
        tickmode='linear',
        tick0=2000,
        dtick=1,
        title='Approximate Release Year'
    ),
    yaxis=dict(
        title='Chip Manufacturer',
        tickmode='array',
        tickvals=y_tick_values,
        ticktext=y_tick_text
    ),
    hovermode='closest'
)

fig.update_xaxes(range=[min(df["Apprx Release"]) - 0.5,
                        max(df["Apprx Release"]) + 0.5])

# Write the plot to site/index.html using the template
os.makedirs("site", exist_ok=True)
with open(os.path.join("web", "template.html"), encoding="utf-8") as template_file:
    page = template_file.read()
plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
with open(os.path.join("site", "index.html"), "w", encoding="utf-8") as output_file:
    output_file.write(page.replace("<!--PLOT-->", plot_html, 1))
