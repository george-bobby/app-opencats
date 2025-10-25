from apps.odoosales.config.constants import QuotationModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def insert_sale_order_header_footer():
    # with Path.open(settings.DATA_PATH.joinpath("header.txt"), encoding="utf-8") as file:
    #     header_text = file.read().strip()
    # with Path.open(settings.DATA_PATH.joinpath("footer.txt"), encoding="utf-8") as file:
    #     footer_text = file.read().strip()

    logger.start("Inserting sale order header and footer...")
    try:
        # Encode text as base64 for binary fields
        # header_b64 = base64.b64encode(header_text.encode("utf-8")).decode("utf-8")
        # footer_b64 = base64.b64encode(footer_text.encode("utf-8")).decode("utf-8")

        data = [
            {
                "document_type": "header",
                "name": "Spring Promo 2025",
                # "datas": header_b64,
            },
            {
                "document_type": "footer",
                "name": "Holiday Thanks",
                # "datas": footer_b64,
            },
        ]

        async with OdooClient() as client:
            try:
                result = await client.create(QuotationModelName.QUOTATION_DOCUMENT.value, [data])
                logger.succeed("Sale order header and footer inserted successfully.")
                return result
            except Exception as e:
                raise ValueError(f"Error inserting sale order header and footer: {e}")

    except FileNotFoundError as e:
        logger.fail(f"File not found: {e}")
        raise
    except UnicodeDecodeError as e:
        logger.fail(f"Unicode decode error: {e}")
        raise
    except Exception as e:
        raise ValueError(f"Unexpected error: {e}")
