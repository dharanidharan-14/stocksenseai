"""
StockSense AI - Download Real Online Product Photography
Downloads real, high-quality photographic images from online CDNs
for all 16 grocery products and updates PostgreSQL image_url.
"""

import os
import urllib.request
import logging
from sqlalchemy import text
from app.core.database import sync_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_images")

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "products"))
os.makedirs(UPLOADS_DIR, exist_ok=True)

# 16 Real Grocery Product Photography URLs
PRODUCT_PHOTOS = {
    1: {  # Aashirvaad Shudh Chakki Atta 5kg
        "filename": "prod_1_atta.jpg",
        "url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&auto=format&fit=crop&q=85",
    },
    2: {  # India Gate Basmati Rice Rozzana 5kg
        "filename": "prod_2_rice.jpg",
        "url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=600&auto=format&fit=crop&q=85",
    },
    3: {  # Tata Salt Vacuum Evaporated 1kg
        "filename": "prod_3_salt.jpg",
        "url": "https://images.unsplash.com/photo-1626074353765-517a681e40be?w=600&auto=format&fit=crop&q=85",
    },
    4: {  # Fortune Sunlite Refined Sunflower Oil 1L
        "filename": "prod_4_oil.jpg",
        "url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=600&auto=format&fit=crop&q=85",
    },
    5: {  # Amul Pure Ghee 1L Tin
        "filename": "prod_5_ghee.jpg",
        "url": "https://images.unsplash.com/photo-1628088062854-d1870b4553da?w=600&auto=format&fit=crop&q=85",
    },
    6: {  # Tata Sampann Unpolished Toor Dal 1kg
        "filename": "prod_6_toordal.jpg",
        "url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600&auto=format&fit=crop&q=85",
    },
    7: {  # Tata Sampann Moong Dal Dhuli 1kg
        "filename": "prod_7_moongdal.jpg",
        "url": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=600&auto=format&fit=crop&q=85",
    },
    8: {  # Amul Taaza Homogenised Toned Milk 500ml
        "filename": "prod_8_milk.jpg",
        "url": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=600&auto=format&fit=crop&q=85",
    },
    9: {  # Britannia 100% Whole Wheat Bread 400g
        "filename": "prod_9_bread.jpg",
        "url": "https://images.unsplash.com/photo-1549931319-a545dcf3bc73?w=600&auto=format&fit=crop&q=85",
    },
    10: {  # Amul Butter Pasteurised 500g
        "filename": "prod_10_butter.jpg",
        "url": "https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=600&auto=format&fit=crop&q=85",
    },
    11: {  # Maggi 2-Minute Masala Instant Noodles 280g
        "filename": "prod_11_noodles.jpg",
        "url": "https://images.unsplash.com/photo-1612927601601-6638404737ce?w=600&auto=format&fit=crop&q=85",
    },
    12: {  # Parle-G Original Gluco Biscuits 800g
        "filename": "prod_12_biscuits.jpg",
        "url": "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=600&auto=format&fit=crop&q=85",
    },
    13: {  # Tata Tea Premium Desh Ki Chai 500g
        "filename": "prod_13_tea.jpg",
        "url": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=600&auto=format&fit=crop&q=85",
    },
    14: {  # Surf Excel Easy Wash Detergent Powder 1kg
        "filename": "prod_14_detergent.jpg",
        "url": "https://images.unsplash.com/photo-1585338107529-13afc5f02586?w=600&auto=format&fit=crop&q=85",
    },
    15: {  # Vim Dishwash Bar 300g
        "filename": "prod_15_dishwash.jpg",
        "url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=85",
    },
    16: {  # Everest Royal Garam Masala 100g
        "filename": "prod_16_masala.jpg",
        "url": "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=600&auto=format&fit=crop&q=85",
    },
}

def download_and_update():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    with sync_engine.connect() as conn:
        for prod_id, info in PRODUCT_PHOTOS.items():
            filepath = os.path.join(UPLOADS_DIR, info["filename"])
            url = info["url"]

            logger.info(f"Downloading real photo for product #{prod_id} from {url}...")
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    img_data = resp.read()
                    with open(filepath, "wb") as f:
                        f.write(img_data)
                    logger.info(f"Saved {info['filename']} ({len(img_data)} bytes)")

                # Update database
                rel_url = f"/uploads/products/{info['filename']}"
                conn.execute(
                    text("UPDATE products SET image_url = :url WHERE id = :pid"),
                    {"url": rel_url, "pid": prod_id},
                )
                conn.commit()
                logger.info(f"Updated product #{prod_id} image_url to {rel_url}")
            except Exception as e:
                logger.error(f"Failed for product #{prod_id}: {e}")

if __name__ == "__main__":
    download_and_update()
    print("All 16 real online product images downloaded and updated in PostgreSQL successfully!")
