const qqMusic = require("./index");

qqMusic
  .api("song", { songmid: "002MJNqB02SZX3" })
  .then((res) => console.log("result", res))
  .catch((err) => console.error("error: ", err.message));
