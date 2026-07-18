from __future__ import annotations

import json
import shutil
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


DIST = ROOT / "dist"
CLIENT = DIST / "client"
SERVER = DIST / "server"


PRECOMPUTED_PHRASES = {
    *app.bootstrap_payload()["examples"]["recommend"],
    *app.bootstrap_payload()["examples"]["search"],
    "少点跑鞋，今天想看看家居",
    "我想看水杯",
    "想看看杯子",
    "保持当前条件",
}


STATIC_ENGINE = r"""
(function () {
  const bootstrap = __BOOTSTRAP__;
  const precomputed = __INTENTS__;
  const products = new Map(bootstrap.products.map((item) => [item.id, item]));
  const groupPrefixes = {
    rental: "rental-",
    concert: "concert-",
    fitness: "fitcase-",
    wow: "wow-",
    inspiration: "happy-",
  };
  const categoryAliases = {
    "裙子": "连衣裙", "连衣裙": "连衣裙", "水杯": "水杯", "杯子": "水杯",
    "跑鞋": "跑鞋", "运动鞋": "运动鞋", "家居": "家居", "防晒": "防晒霜",
    "防晒霜": "防晒霜", "投影仪": "投影仪", "口红": "口红", "耳机": "耳机",
    "手机": "手机", "咖啡机": "咖啡机", "猫粮": "猫粮", "帐篷": "帐篷",
    "键盘": "键盘", "香水": "香水", "水果": "水果", "零食": "零食"
  };

  function normalize(value) {
    return String(value || "").replace(/[\s，。！？、,.!?“”"'：:；;]/g, "");
  }

  const normalizedIntents = new Map(
    Object.entries(precomputed).map(([phrase, intent]) => [normalize(phrase), intent])
  );

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function slot(name, operator, value, strength, label) {
    return { name, operator, value, strength, label };
  }

  function unknownIntent(transcript) {
    return {
      type: "unknown",
      mode: "unknown",
      modeLabel: "即时意图",
      polarity: "neutral",
      slots: [],
      scope: "session",
      transcript,
      confidence: 0.2,
      evidence: [],
      route: { name: "none", label: "即时意图" },
    };
  }

  function inferIntent(transcript) {
    const text = normalize(transcript);
    if (normalizedIntents.has(text)) return clone(normalizedIntents.get(text));

    const presetMatchers = [
      ["好看的裙子", "给我推荐一些好看的裙子"],
      ["韩式", "想要韩式风格"], ["韩系", "想要韩式风格"],
      ["颜色浅一点", "想要颜色浅一点"], ["浅色", "想要颜色浅一点"],
      ["健身", "给我推荐点健身好物"],
      ["眼前一亮", "有没有让我眼前一亮的好物"],
      ["出租屋", "我的出租屋还能更舒服吗？"],
      ["演唱会", "我要去看演唱会有什么推荐好物"],
      ["提升幸福感", "买什么东西可以提升幸福感"],
      ["防晒霜", "有什么好用的防晒霜"],
    ];
    for (const [needle, phrase] of presetMatchers) {
      if (text.includes(normalize(needle))) return clone(normalizedIntents.get(normalize(phrase)));
    }

    const slots = [];
    for (const [alias, value] of Object.entries(categoryAliases)) {
      if (text.includes(alias)) {
        const negative = text.includes(`不要${alias}`) || text.includes(`少点${alias}`);
        slots.push(slot("category", negative ? "neq" : "eq", value, "soft",
          `${negative ? "减少" : "增加"}${value}`));
        break;
      }
    }
    const priceMatch = text.match(/(\d+)元?(以内|以下|不超过)/);
    if (priceMatch) slots.push(slot("price", "lte", Number(priceMatch[1]), "hard", `≤¥${priceMatch[1]}`));
    if (text.includes("韩式") || text.includes("韩系")) {
      slots.push(slot("style", "eq", "韩式", "soft", "韩式风格"));
    }
    if (text.includes("浅一点") || text.includes("浅色")) {
      slots.push(slot("attribute", "eq", "浅色", "soft", "浅色"));
    }
    if (!slots.length) return unknownIntent(transcript);
    return {
      type: slots.some((item) => item.operator === "neq") ? "exclude" : "pull",
      mode: "product",
      modeLabel: "即时意图",
      polarity: "positive",
      slots,
      scope: "session",
      transcript,
      confidence: 0.78,
      evidence: slots.map((item) => item.label),
      route: { name: "constraint_ranking", label: "即时意图" },
    };
  }

  function intentSourceKey(intent) {
    return intent?.scenario?.key || intent?.exploreTheme || null;
  }

  function mergeConditions(existing, intent) {
    const result = clone(existing || []);
    const sourceKey = intentSourceKey(intent);
    for (const original of intent.slots || []) {
      const incoming = {
        ...clone(original),
        sourceMode: intent.mode,
        ...(sourceKey ? { sourceKey } : {}),
      };
      for (let index = result.length - 1; index >= 0; index -= 1) {
        const current = result[index];
        const sameValue = current.name === incoming.name && current.value === incoming.value;
        const replacePrice = current.name === "price" && incoming.name === "price";
        if (sameValue || replacePrice) result.splice(index, 1);
      }
      result.push(incoming);
    }
    return result;
  }

  function itemContains(item, value) {
    return item.category === value ||
      item.attributes.includes(value) ||
      (item.styles || []).includes(value) ||
      (item.audiences || []).includes(value) ||
      (item.goals || []).includes(value) ||
      item.brand === value ||
      (value === "家居" && item.category === "收纳") ||
      (value === "运动鞋" && ["跑鞋", "休闲鞋"].includes(item.category));
  }

  function conditionMatches(item, condition) {
    if (condition.name === "price") return item.price <= Number(condition.value);
    return itemContains(item, condition.value);
  }

  function rank(session, intent) {
    const sourceCondition = [...session].reverse().find((item) => item.sourceKey);
    const sourceKey = intentSourceKey(intent) || sourceCondition?.sourceKey;
    const prefix = groupPrefixes[sourceKey];
    const scored = [];
    for (const item of bootstrap.products) {
      let score = item.baseScore || 0;
      let blocked = false;
      for (const condition of session) {
        const matches = conditionMatches(item, condition);
        if (condition.operator === "neq" && matches) {
          blocked = true;
          break;
        }
        if (condition.operator === "lte" && !matches && condition.strength === "hard") {
          blocked = true;
          break;
        }
        if (condition.operator === "eq") score += matches ? 70 : -12;
      }
      if (blocked) continue;
      if (prefix && item.id.startsWith(prefix)) score += 800;
      scored.push([score, item.id]);
    }
    scored.sort((left, right) => right[0] - left[0]);
    return scored.map((entry) => entry[1]);
  }

  async function staticApi(path, options = {}) {
    if (path === "/api/demo/bootstrap") return clone(bootstrap);
    if (path === "/api/intent/reset") {
      return {
        sessionIntent: [],
        resultIds: clone(bootstrap.initialRecommendations),
        searchResultIds: clone(bootstrap.initialSearchResults),
        feedback: "已恢复初始推荐",
      };
    }
    if (path === "/api/intent/apply") {
      const payload = JSON.parse(options.body || "{}");
      const intent = inferIntent(payload.transcript);
      const sessionIntent = mergeConditions(payload.sessionIntent || [], intent);
      const resultIds = rank(sessionIntent, intent);
      return {
        intent,
        engine: {
          mode: intent.mode,
          modeLabel: "即时意图",
          confidence: intent.confidence,
          evidence: intent.evidence,
          route: intent.route,
        },
        sessionIntent,
        resultIds,
        nearMatchIds: [],
        feedback: intent.type === "unknown"
          ? "我还没听懂。可以说具体商品、生活场景，或想探索的新灵感。"
          : `已应用：${(intent.slots || []).map((item) => item.label).join(" · ")}`,
      };
    }
    throw new Error("接口不存在");
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function (input, options = {}) {
    const url = new URL(typeof input === "string" ? input : input.url, window.location.href);
    if (!url.pathname.startsWith("/api/")) return nativeFetch(input, options);
    try {
      const payload = await staticApi(url.pathname, options);
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 400,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
  };
})();
"""


WORKER = r"""
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/recommend" || url.pathname === "/search") {
      url.pathname = "/index.html";
      return env.ASSETS.fetch(new Request(url, request));
    }
    return env.ASSETS.fetch(request);
  },
};
"""


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", CLIENT)
    SERVER.mkdir(parents=True, exist_ok=True)

    bootstrap = app.bootstrap_payload()
    intents = {phrase: app.parse_intent(phrase) for phrase in sorted(PRECOMPUTED_PHRASES)}
    engine = STATIC_ENGINE.replace(
        "__BOOTSTRAP__",
        json.dumps(bootstrap, ensure_ascii=False, separators=(",", ":")),
    ).replace(
        "__INTENTS__",
        json.dumps(intents, ensure_ascii=False, separators=(",", ":")),
    )
    (CLIENT / "demo-static.js").write_text(engine, encoding="utf-8")

    index_path = CLIENT / "index.html"
    index = index_path.read_text(encoding="utf-8")
    script_marker = '<script src="/app.js'
    index = index.replace(script_marker, '<script src="/demo-static.js"></script>\n  ' + script_marker, 1)
    index_path.write_text(index, encoding="utf-8")
    (SERVER / "index.js").write_text(WORKER.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
