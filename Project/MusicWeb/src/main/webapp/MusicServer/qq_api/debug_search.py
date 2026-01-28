import asyncio
from qqmusic_api import search, song, login
from qqmusic_api.login import QRLoginType, QRCodeLoginEvents, PhoneLoginEvents
from qqmusic_api import Credential

async def main():
    try:
        print("Testing quick_search...")
        res1 = await search.quick_search("周杰伦")
        print("quick_search keys:", res1.keys())
        if 'song' in res1:
             print("quick_search song count:", len(res1['song']['itemlist']))
    except Exception as e:
        print(f"quick_search failed: {e}")

    try:
        print("Testing general_search...")
        res2 = await search.general_search("周杰伦")
        # print("general_search result keys:", res2.keys())
        # general_search structure is complex, usually 'data' -> 'body' -> ...
        # But qqmusic-api usually returns the processed data?
        # general_search returns 'no processor' tuple?
        # In search.py: return {...}, NO_PROCESSOR
        # So res2 might be the raw dict from API response?
        # Wait, if NO_PROCESSOR is used, `api_request` returns the JSON directly?
        print("general_search verification:", "meta" in str(res2) or "body" in str(res2))
    except Exception as e:
        print(f"general_search failed: {e}")
            
    try:
        print("Retrying search_by_type with num=30...")
        result = await search.search_by_type(keyword="周杰伦", num=30, page=1)
        print("search_by_type result len:", len(result))
    except Exception as e:
        print(f"search_by_type failed with num=30: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
