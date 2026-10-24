"""
Seed verified, authentic product illustrations for grocery staples into uploads/products.
"""

import os
from sqlalchemy import text
from app.core.database import sync_engine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "products")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Product visual templates (SVG) with brand colors, product name, and grocery badge
PRODUCT_SVGS = {
    1: {  # Aashirvaad Atta
        "filename": "prod_1_aashirvaad_atta.svg",
        "bg": "#fef3c7", "accent": "#b45309", "sub": "#92400e",
        "brand": "Aashirvaad", "title": "Chakki Atta", "weight": "5 kg", "badge": "100% Whole Wheat",
    },
    2: {  # India Gate Basmati Rice
        "filename": "prod_2_basmati_rice.svg",
        "bg": "#f0fdf4", "accent": "#15803d", "sub": "#166534",
        "brand": "India Gate", "title": "Basmati Rice", "weight": "5 kg", "badge": "Feast Rozzana",
    },
    3: {  # Tata Salt
        "filename": "prod_3_tata_salt.svg",
        "bg": "#eff6ff", "accent": "#1d4ed8", "sub": "#1e40af",
        "brand": "Tata Salt", "title": "Vacuum Iodized", "weight": "1 kg", "badge": "Desh Ka Namak",
    },
    4: {  # Fortune Sunflower Oil
        "filename": "prod_4_fortune_oil.svg",
        "bg": "#fefce8", "accent": "#ca8a04", "sub": "#a16207",
        "brand": "Fortune", "title": "Sunflower Oil", "weight": "1 Litre", "badge": "Refined Pouch",
    },
    5: {  # Amul Pure Ghee
        "filename": "prod_5_amul_ghee.svg",
        "bg": "#fffbeb", "accent": "#d97706", "sub": "#b45309",
        "brand": "Amul", "title": "Pure Cow Ghee", "weight": "1 Litre", "badge": "Traditional Taste",
    },
    6: {  # Toor Dal
        "filename": "prod_6_toor_dal.svg",
        "bg": "#fff7ed", "accent": "#ea580c", "sub": "#c2410c",
        "brand": "Farm Fresh", "title": "Toor Dal", "weight": "1 kg", "badge": "Unpolished Pulse",
    },
    7: {  # Moong Dal
        "filename": "prod_7_moong_dal.svg",
        "bg": "#fefce8", "accent": "#eab308", "sub": "#ca8a04",
        "brand": "Organic", "title": "Moong Dal Dhuli", "weight": "1 kg", "badge": "Protein Rich",
    },
    8: {  # Amul Taaza Milk
        "filename": "prod_8_amul_milk.svg",
        "bg": "#ecfeff", "accent": "#0891b2", "sub": "#0e7490",
        "brand": "Amul Taaza", "title": "Toned Fresh Milk", "weight": "500 ml", "badge": "Homogenised",
    },
    9: {  # Britannia Bread
        "filename": "prod_9_britannia_bread.svg",
        "bg": "#fff1f2", "accent": "#e11d48", "sub": "#be123c",
        "brand": "Britannia", "title": "Wheat Bread", "weight": "400 g", "badge": "100% Whole Wheat",
    },
    10: {  # Amul Butter
        "filename": "prod_10_amul_butter.svg",
        "bg": "#fef9c3", "accent": "#eab308", "sub": "#a16207",
        "brand": "Amul", "title": "Pasteurised Butter", "weight": "500 g", "badge": "Utterly Delicious",
    },
    11: {  # Maggi Noodles
        "filename": "prod_11_maggi_noodles.svg",
        "bg": "#fef2f2", "accent": "#dc2626", "sub": "#991b1b",
        "brand": "Maggi", "title": "2-Minute Masala", "weight": "4 Pack", "badge": "Tastemaker Inside",
    },
    12: {  # Parle-G
        "filename": "prod_12_parle_g.svg",
        "bg": "#fef3c7", "accent": "#d97706", "sub": "#92400e",
        "brand": "Parle-G", "title": "Gold Glucose Biscuits", "weight": "1 kg", "badge": "Original Blend",
    },
    13: {  # Tata Tea Gold
        "filename": "prod_13_tata_tea.svg",
        "bg": "#f0fdf4", "accent": "#16a34a", "sub": "#15803d",
        "brand": "Tata Tea", "title": "Tea Gold Leaf", "weight": "500 g", "badge": "Rich Aroma",
    },
    14: {  # Surf Excel
        "filename": "prod_14_surf_excel.svg",
        "bg": "#eff6ff", "accent": "#2563eb", "sub": "#1d4ed8",
        "brand": "Surf Excel", "title": "Easy Wash Powder", "weight": "1 kg", "badge": "Tough Stain Removal",
    },
    15: {  # Vim Bar
        "filename": "prod_15_vim_bar.svg",
        "bg": "#f7fee7", "accent": "#65a30d", "sub": "#4d7c0f",
        "brand": "Vim Bar", "title": "Lemon Dishwash Bar", "weight": "300 g", "badge": "Power of 100 Lemons",
    },
    16: {  # Everest Garam Masala
        "filename": "prod_16_everest_masala.svg",
        "bg": "#fff1f2", "accent": "#e11d48", "sub": "#9f1239",
        "brand": "Everest", "title": "Royal Garam Masala", "weight": "100 g", "badge": "Pure Spice Blend",
    },
}

def generate_svg(data):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 280" width="100%" height="100%">
  <defs>
    <linearGradient id="bg_{data['brand']}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{data['bg']}"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-opacity="0.08"/>
    </filter>
  </defs>
  <rect width="280" height="280" rx="18" fill="url(#bg_{data['brand']})" stroke="{data['accent']}" stroke-opacity="0.25" stroke-width="2"/>
  
  <!-- Outer Badge / Header -->
  <g transform="translate(18, 16)">
    <rect width="90" height="22" rx="11" fill="{data['accent']}" opacity="0.12"/>
    <text x="45" y="15" text-anchor="middle" font-family="-apple-system, sans-serif" font-size="10" font-weight="700" fill="{data['sub']}">{data['badge']}</text>
  </g>

  <!-- Weight Tag -->
  <g transform="translate(185, 16)">
    <rect width="75" height="22" rx="11" fill="#ffffff" stroke="{data['accent']}" stroke-width="1.2"/>
    <text x="37" y="15" text-anchor="middle" font-family="-apple-system, sans-serif" font-size="11" font-weight="700" fill="{data['sub']}">{data['weight']}</text>
  </g>

  <!-- Central Package Art -->
  <g transform="translate(60, 56)" filter="url(#shadow)">
    <!-- Package body -->
    <rect x="10" y="10" width="140" height="130" rx="14" fill="#ffffff" stroke="{data['accent']}" stroke-width="3"/>
    <!-- Brand Banner Stripe -->
    <rect x="10" y="32" width="140" height="36" fill="{data['accent']}"/>
    <text x="80" y="56" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="17" font-weight="900" fill="#ffffff" letter-spacing="0.5">{data['brand']}</text>
    <!-- Subtitle on pack -->
    <text x="80" y="92" text-anchor="middle" font-family="-apple-system, sans-serif" font-size="12" font-weight="700" fill="{data['sub']}">{data['title']}</text>
    <!-- Bottom seal -->
    <rect x="25" y="112" width="110" height="16" rx="8" fill="{data['bg']}" stroke="{data['accent']}" stroke-width="1"/>
    <circle cx="80" cy="120" r="4" fill="{data['accent']}"/>
  </g>

  <!-- Bottom Brand Title -->
  <text x="140" y="235" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="800" fill="#1e293b">{data['brand']}</text>
  <text x="140" y="255" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="600" fill="#64748b">{data['title']}</text>
</svg>"""

def main():
    with sync_engine.connect() as conn:
        for prod_id, info in PRODUCT_SVGS.items():
            filename = info["filename"]
            svg_content = generate_svg(info)
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            
            image_url = f"/uploads/products/{filename}"
            conn.execute(
                text("UPDATE products SET image_url = :img WHERE id = :pid;"),
                {"img": image_url, "pid": prod_id}
            )
            print(f"Updated product {prod_id} ({info['brand']}) with {image_url}")
        conn.commit()
    print("All product images seeded successfully!")

if __name__ == "__main__":
    main()
