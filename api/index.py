from flask import Flask, request, jsonify
import re
from rapidfuzz import process, utils

app = Flask(__name__)

PRODUCT_LIST = [
    "iPhone 16",
    "Samsung Galaxy S25",
    "Google Pixel 9",
    "MacBook Pro 2025",
    "Dell XPS 15",
    "Sony WH-1000XM6",
    "Bose QuietComfort Ultra",
    "Apple Watch Series 10"
]

def parse_products_text(text):
    product_index = []
    for product in PRODUCT_LIST:
        alignment = process.extractOne(
            product,
            text,
            processor=utils.default_process,
            scorer=process.partial_ratio_alignment,
            score_cutoff=90
        )
        if alignment:
            matched_product = alignment[0]
            start = alignment[-1].dest_start
            end = alignment[-1].dest_end
            product_index.append((matched_product, start, end))

    # Quantity extraction pattern
    quant_pattern = r'\b\d{1,6}\s?(?:units|pack|meter|kilogram|l|liter|g|m|kg|ml)\b'
    quantities = re.findall(quant_pattern, text, flags=re.IGNORECASE)
    
    # Sort products by occurrence position
    product_index.sort(key=lambda x: x[1])
    products_ordered = [p[0] for p in product_index]
    
    response = {}
    errors = []

    # Duplicate product check
    seen = set()
    duplicates = set()
    for product in products_ordered:
        if product in seen:
            duplicates.add(product)
        else:
            seen.add(product)
    
    if duplicates:
        errors.append(f"Duplicate products: {', '.join(duplicates)}")

    # Quantity mismatch check
    product_count = len(products_ordered)
    quantity_count = len(quantities)
    if product_count != quantity_count:
        errors.append(f"Product-quantity mismatch ({product_count} vs {quantity_count})")

    # Build response
    for idx, product in enumerate(products_ordered):
        response[product] = quantities[idx] if idx < quantity_count else "Quantity missing"

    # Set flags and logs
    if errors:
        response.update({
            "flag": 1,
            "log": " | ".join(errors)
        })
    else:
        response["flag"] = 0

    return response if products_ordered else {"flag": 1, "log": "No products detected"}

@app.route('/', methods=['POST'])
def process_text():
    data = request.json
    text = data.get('text', '')
    result = parse_products_text(text)
    return jsonify(result)

# Test route for quick verification
@app.route('/test', methods=['GET'])
def test_endpoint():
    sample_text = """Order details:
    - iPhone 16 100 units
    - iPhone 16 50 units
    - Samsung Galaxy S25 200 units
    Please process this immediately."""
    
    result = parse_products_text(sample_text)
    return jsonify({
        "test_input": sample_text,
        "test_output": result
    })

if __name__ == '__main__':
    app.run()
