module.exports = {
  // 搜索
  "/": async ({ req, res, request, cache }) => {
    let {
      pageNo = 1,
      pageSize = 20,
      key,
      t = 0, // 0：单曲，2：歌单，7：歌词，8：专辑，9：歌手，12：mv
      raw,
    } = req.query;
    let total = 0;

    if (!key) {
      return res.send({
        result: 500,
        errMsg: "关键词不能为空",
      });
    }

    const cacheKey = `search_${key}_${pageNo}_${pageSize}_${t}`;
    const cacheData = cache.get(cacheKey);
    if (cacheData) {
      res && res.send(cacheData);
      return cacheData;
    }
    const url = "https://u.y.qq.com/cgi-bin/musicu.fcg";
    // 0：单曲
    // 1：歌手
    // 2：专辑
    // 3：歌单
    // 4：mv
    // 7：歌词
    // 8：用户

    let data = {
      "music.search.SearchCgiService": {
        method: "DoSearchForQQMusicDesktop",
        module: "music.search.SearchCgiService",
        param: {
          num_per_page: pageSize,
          page_num: pageNo,
          query: key,
          search_type: t,
        },
      },
    };

    const result = await request({
      url,
      method: "post",
      data,
      headers: {
        Referer: "https://y.qq.com",
      },
    });

    if (Number(raw)) {
      return res.send(result);
    }

    // 下面是数据格式的美化
    const { keyword, sum, perpage, curpage } =
      result["music.search.SearchCgiService"].data.meta;

    const searchResult =
      result["music.search.SearchCgiService"].data.body.song.list || [];
    //   (keyMap[t] ? result.data[keyMap[t]] : result.data) || [];
    const list = searchResult.map((item) => ({
      singer: item.singer, // 、
      name: item.title,
      songid: item.id,
      songmid: item.mid,
      songname: item.title,

      albumid: item.album.id,
      albummid: item.album.mid,
      albumname: item.album.name,
      interval: item.interval,

      strMediaMid: item.file.media_mid,
      size128: item.file.size_128mp3,
      size320: item.file.size_320mp3,
      sizeape: item.file.size_ape,
      sizeflac: item.file.size_flac,
    }));

    pageNo = curpage;
    pageSize = perpage;
    total = sum;

    const resData = {
      result: 100,
      data: {
        list,
        pageNo,
        pageSize,
        total,
        key: keyword || key,
        t,
      },
      // header: req.header(),
      // req: JSON.parse(JSON.stringify(req)),
    };
    cache.set(cacheKey, resData, 120);
    res.send && res.send(resData);
    return resData;
  },
};
