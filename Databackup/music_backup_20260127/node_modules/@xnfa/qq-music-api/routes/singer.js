const cheerio = require("cheerio");

module.exports = {
  // 获取歌手介绍
  "/desc": async ({ req, res, cache, request }) => {
    const { singermid, raw } = req.query;

    let cacheKey = `singer_desc_${singermid}_${raw}`;
    let cacheData = cache.get(cacheKey);
    if (cacheData) {
      return res.send(cacheData);
    }
    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }
    let result = await request(
      {
        url: "http://c.y.qq.com/splcloud/fcgi-bin/fcg_get_singer_desc.fcg",
        data: {
          singermid,
          format: "xml",
          utf8: 1,
          outCharset: "utf-8",
        },
        headers: {
          Referer: "https://y.qq.com",
        },
      },
      {
        dataType: "xml",
      }
    );

    const page = await request(
      {
        url: `https://y.qq.com/n/yqq/singer/${singermid}.html`,
      },
      {
        dataType: "raw",
      }
    );

    const $ = cheerio.load(page);

    const info = result.result.data.info || {};

    info.singername = $(".data__name .data__name_txt").text();

    ["basic", "other"].forEach((k) => {
      info[k] &&
        info[k].item &&
        !Array.isArray(info[k].item) &&
        (info[k].item = [info[k].item]);
    });

    if (!Number(raw)) {
      result = {
        result: 100,
        data: info,
      };
    }
    res.send(result);
    cache.set(cacheKey, result, 24 * 60);
  },

  "/desc/new": async ({ req, res, cache, request }) => {
    const { singermid } = req.query;

    let cacheKey = `singer_desc_new_${singermid}`;
    let cacheData = cache.get(cacheKey);
    if (cacheData) {
      return res.send(cacheData);
    }
    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }

    const result = await request({
      url: "http://u.y.qq.com/cgi-bin/musicu.fcg",
      data: {
        data: JSON.stringify({
          req_0: {
            module: "music.musichallSinger.SingerInfoInter",
            method: "GetSingerDetail",
            param: {
              singer_mids: [singermid],
              pic: 1,
              group_singer: 1,
              wiki_singer: 1,
              ex_singer: 1,
            },
          },
          req_1: {
            module: "music.musichallSong.SongListInter",
            method: "GetSingerSongList",
            param: {
              singerMid: singermid,
              begin: 0,
              num: 10,
              order: 1,
            },
          },
          req_2: {
            module: "music.musichallAlbum.AlbumListServer",
            method: "GetAlbumList",
            param: {
              singerMid: singermid,
              order: 1,
              num: 30,
              begin: 0,
            },
          },
          req_6: {
            module: "MvService.MvInfoProServer",
            method: "GetSingerMvList",
            param: {
              singerid: 0,
              singermid: singermid,
              tagid: 0,
              start: 0,
              count: 6,
              order: 1,
            },
          },
          comm: {
            uin: "0",
            format: "json",
            ct: 6,
            cv: 80507,
            platform: "wk_v17",
          },
        }),
      },
    });

    cacheData = {
      result: 100,
      data: {
        ...result.req_0.data.singer_list[0],
        song: result.req_1.data,
        album: result.req_2.data,
        mv: result.req_6.data,
        singermid,
      },
    };
    res.send(cacheData);
    cache.set(cacheKey, cacheData);
  },

  // 获取歌手专辑
  "/album": async ({ req, res, cache, request }) => {
    const { singermid, pageNo = 1, pageSize = 20, raw } = req.query;

    let cacheKey = `singer_album_${singermid}_${pageNo}_${pageSize}_${raw}`;
    let cacheData = cache.get(cacheKey);
    if (cacheData) {
      return res.send(cacheData);
    }
    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }

    const result = await request({
      url: "http://u.y.qq.com/cgi-bin/musicu.fcg",
      data: {
        data: JSON.stringify({
          comm: {
            ct: 24,
            cv: 0,
          },
          singerAlbum: {
            method: "get_singer_album",
            param: {
              singermid,
              order: "time",
              begin: (pageNo - 1) * pageSize,
              num: pageSize / 1,
              exstatus: 1,
            },
            module: "music.web_singer_info_svr",
          },
        }),
      },
    });

    if (Number(raw)) {
      res.send(result);
    } else {
      const {
        list,
        singer_id: id,
        singer_mid: singermid,
        singer_name: name,
        total,
      } = result.singerAlbum.data;
      cacheData = {
        result: 100,
        data: {
          list,
          id,
          singermid,
          name,
          total,
          pageNo,
          pageSize,
        },
      };
      res.send(cacheData);
      cache.set(cacheKey, cacheData, 2 * 60);
    }
  },

  // 获取热门歌曲
  "/songs": async ({ req, res, cache, request }) => {
    const { singermid, begin = 0, num, order = 1 } = req.query;
    const pageSize = num ? parseInt(num) : 10;

    let cacheKey = `singer_album_${singermid}_${begin}_${num}_${order}`;
    let cacheData = cache.get(cacheKey);
    if (cacheData) {
      return res.send(cacheData);
    }
    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }

    const result = await request({
      url: "http://u.y.qq.com/cgi-bin/musicu.fcg",
      data: {
        data: JSON.stringify({
          req_0: {
            module: "music.musichallSong.SongListInter",
            method: "GetSingerSongList",
            param: {
              singerMid: singermid,
              begin: begin,
              num: pageSize,
              order: order,
            },
          },
          comm: {
            ct: 6,
            cv: 0,
          },
        }),
      },
    });

    const { songList: list, totalNum } = result.req_0.data;
    cacheData = {
      result: 100,
      data: {
        list: list.map((v) => v.songInfo),
        total: totalNum,
        num: pageSize,
        singermid,
      },
    };
    res.send(cacheData);
    cache.set(cacheKey, cacheData);
  },

  // 获取mv
  "/mv": async ({ req, res, request }) => {
    const { singermid, pageNo = 1, pageSize = 20, raw } = req.query;

    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }

    const result = await request({
      url: "http://c.y.qq.com/mv/fcgi-bin/fcg_singer_mv.fcg",
      data: {
        singermid,
        order: "time",
        begin: (pageNo - 1) * pageSize,
        num: pageSize,
        cid: 205360581,
      },
    });

    if (Number(raw)) {
      res.send(result);
    } else {
      res.send({
        result: 100,
        data: {
          ...result.data,
          pageNo,
          pageSize,
          singermid,
        },
      });
    }
  },

  // 相似歌手
  "/sim": async ({ req, res, request }) => {
    const { singermid, raw } = req.query;

    if (!singermid) {
      return res.send({
        result: 500,
        errMsg: "singermid 不能为空",
      });
    }

    const result = await request({
      url: "http://c.y.qq.com/v8/fcg-bin/fcg_v8_simsinger.fcg",
      data: {
        singer_mid: singermid,
        num: 10,
        utf8: 1,
      },
    });

    if (Number(raw)) {
      res.send(result);
    } else {
      res.send({
        result: 100,
        data: {
          list: result.singers.items,
          singermid,
        },
      });
    }
  },

  // 获取歌手分类
  "/category": async ({ req, res, request }) => {
    const { raw } = req.query;

    const result = await request({
      url: "https://u.y.qq.com/cgi-bin/musicu.fcg",
      data: {
        data: JSON.stringify({
          comm: { ct: 24, cv: 0 },
          singerList: {
            module: "Music.SingerListServer",
            method: "get_singer_list",
            param: {
              area: -100,
              sex: -100,
              genre: -100,
              index: -100,
              sin: 0,
              cur_page: 1,
            },
          },
        }),
      },
    });

    if (Number(raw)) {
      res.send(result);
    } else {
      res.send({
        result: 100,
        data: result.singerList.data.tags,
      });
    }
  },

  // 根据类型获取歌手列表
  "/list": async ({ req, res, request }) => {
    const {
      area = -100,
      sex = -100,
      genre = -100,
      index = -100,
      pageNo = 1,
      raw,
    } = req.query;

    const result = await request({
      url: "https://u.y.qq.com/cgi-bin/musicu.fcg",
      data: {
        data: JSON.stringify({
          comm: {
            ct: 24,
            cv: 0,
          },
          singerList: {
            module: "Music.SingerListServer",
            method: "get_singer_list",
            param: {
              area: area / 1,
              sex: sex / 1,
              genre: genre / 1,
              index: index / 1,
              sin: (pageNo - 1) * 80,
              cur_page: pageNo / 1,
            },
          },
        }),
      },
    });

    if (Number(raw)) {
      res.send(result);
    } else {
      const trueData = result.singerList.data;
      trueData.list = trueData.singerlist;
      delete trueData.tags;
      delete trueData.singerlist;
      res.send({
        result: 100,
        data: trueData,
      });
    }
  },
};
