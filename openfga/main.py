import asyncio
from openfga_slac.sync import sync_loop

if __name__ == "__main__":
    asyncio.run(sync_loop())