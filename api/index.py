# api/index.py

from flask import Flask, request, jsonify
import json
import re
from rapidfuzz import fuzz, utils
from rapidfuzz.fuzz import partial_ratio_alignment
from collections import Counter

app = Flask(__name__)

def parse_products_text(products, text):
    productindex = []
    for product in products:
        # Find all instances of each product in the text
        alignments = []
        search_text = text
        start_offset = 0
        
        while True:
            alignment = partial_ratio_alignment(product, search_text, processor=utils.default_process, score_cutoff=90)
            if alignment is None:
                break
                
            actual_start = alignment.dest_start + start_offset
            actual_end = alignment.dest_end + start_offset
            alignments.append((actual_start, actual_end))
            
            # Update search text and offset for next iteration
            search_text = search_text[:alignment.dest_start] + ' ' * (alignment.dest_end - alignment.dest_start + 1) + search_text[alignment.dest_end+1:]
            start_offset += alignment.dest_end + 1
        
        # Add all found instances to productindex
        for start, end in alignments:
            productindex.append((product, start, end))
    
    op = {}
    
    if productindex:
        # Sort by position in text
        productindex.sort(key=lambda x: x[1])
        
        # Check for duplicate products
        product_names = [p[0] for p in productindex]
        product_counts = Counter(product_names)
        duplicate_products = [p for p, count in product_counts.items() if count > 1]
        
        # Create a copy of the text for quantity extraction
        working_text = text
        
        # Extract all quantities in order
        quantpattern = r'\d{1,6} units|\d{1,6} pack|\d{1,6} meter|\d{1,6} kilogram|\d{1,6} l|\d{1,6} liter|\d{1,6} g|\d{1,6} m|\d{1,6} kg|\d{1,6} ml'
        quantities = re.findall(quantpattern, working_text)
        
        # Create product-quantity pairs based on order in text
        product_quantity_pairs = []
        unique_products = []
        
        # Match products with quantities in order
        for product, _, _ in productindex:
            if len(quantities) > 0:
                product_quantity_pairs.append((product, quantities.pop(0)))
            else:
                product_quantity_pairs.append((product, "unknown quantity"))
                
            # Track unique products (for duplicate detection)
            if product not in unique_products:
                unique_products.append(product)
        
        # Assemble the output
        if duplicate_products:
            # Flag duplicates but keep correct quantity assignments
            op['flag'] = 1
            duplicate_str = ", ".join(duplicate_products)
            op['reason'] = f"duplicate found: {duplicate_str}"
            
            # Remove duplicate product-quantity pairs while preserving correct assignments
            seen_products = set()
            unique_pairs = []
            
            for product, quantity in product_quantity_pairs:
                if product not in seen_products or product not in duplicate_products:
                    unique_pairs.append((product, quantity))
                    seen_products.add(product)
            
            # Assign quantities to products (keeping one of each duplicate)
            for product, quantity in unique_pairs:
                op[product] = quantity
                
        elif len(product_quantity_pairs) != len(unique_products):
            # This is a safety check - should not trigger with our new logic
            op['flag'] = 1
            op['reason'] = f"mismatch between products and quantities"
            
            # Still assign quantities to products (one per unique product)
            seen_products = set()
            for product, quantity in product_quantity_pairs:
                if product not in seen_products:
                    op[product] = quantity
                    seen_products.add(product)
        else:
            # No duplicates - assign quantities and set flag to 0
            op['flag'] = 0
            seen_products = set()
            for product, quantity in product_quantity_pairs:
                if product not in seen_products:
                    op[product] = quantity
                    seen_products.add(product)
    else:
        op = {'flag': 1, 'reason': 'No products matched in the text'}
    
    return op

@app.route('/api/parser', methods=['POST'])
def parse():
    try:
        data = request.json
        # Extract products and text from request body
        products = data.get('products', [])
        text = data.get('text', '')
        
        if not products or not text:
            return jsonify({"error": "Missing products or text", "flag": 1, "reason": "Missing required input data"}), 400
        
        # Process the data
        result = parse_products_text(products, text)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e), "flag": 1, "reason": "Server error occurred during processing"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Parser API is running. Send POST requests to /api/parser"})
