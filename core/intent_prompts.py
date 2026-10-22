"""追问驱动改写的意图提示库 —— 每个 AI 特征对应的追问方向。

dbs-ai-check 的核心洞见：每个 AI 特征背后都有作者本来想达成的目的。
追问不是为了批评，是为了搞清楚那个目的，然后让作者用自己的方式去达成。
"""

from .models import IntentPrompt

# 意图提示映射表
INTENT_PROMPTS: dict[int, IntentPrompt] = {}

def _reg(p: IntentPrompt):
    INTENT_PROMPTS[p.dimension_id] = p

# ── 根因型 ──

_reg(IntentPrompt(
    dimension_id=6,
    intent_desc="展示确定性和权威感",
    prompt="你这篇文章里有没有什么地方你其实也不太确定？写出来。读者能感觉到真的犹豫和假的自信。",
    self_check="不用「你可能会觉得」开头，不假设用户有犹豫。直接问是否存在不确定的地方。",
))

_reg(IntentPrompt(
    dimension_id=16,
    intent_desc="让观点听起来重要、值得关注",
    prompt="你用了套话开头的写法。删掉它，文章会不会更短但意思不变？试一下。",
    self_check="不评价套话好不好，只让用户做一个删掉后的比较。",
))

_reg(IntentPrompt(
    dimension_id=10,
    intent_desc="让表达听起来正式、专业",
    prompt="这句话你嘴上会怎么说？那就怎么写。特别注意「作为」「基于」「进行」这些词。",
    self_check="追问本身不用被动语态和书面词。用「你嘴上会怎么说」这种口语表达。",
))

# ── 并发型 ──

_reg(IntentPrompt(
    dimension_id=1,
    intent_desc="制造节奏感和结构清晰度",
    prompt="这几句排比里，哪一句是你最想说的？把那一句加长或者换个说法，打破均匀。",
    self_check="不用模板句式提问。直接指向「哪一句你真正想说」。",
))

_reg(IntentPrompt(
    dimension_id=4,
    intent_desc="让句子听起来有气势",
    prompt="你随便挑五句话数一下字数，是不是都差不多长？试试在某个地方加一句两三个字的短句。",
    self_check="提问本身句长要有变化。不用工整的并列结构。",
))

# ── 独立型 ──

_reg(IntentPrompt(
    dimension_id=7,
    intent_desc="赋予事件更大的意义",
    prompt="你用「历史性时刻」来描述这件事。如果不用这个词，你会怎么说？保留事物本来的大小。",
    self_check="不用比喻、不用抽象升华。直接问用户不用这个词怎么说。",
))

_reg(IntentPrompt(
    dimension_id=8,
    intent_desc="强调认知高差——翻转读者的预期",
    prompt="你用了「不是……而是……」或二元对立的句式。把这些转折词全删掉，直接白描你想说的那个事实，信息量少了吗？如果没少，留事实就好，不用修辞教训人。",
    self_check="问句本身不用「不是X而是Y」结构，引导直陈白描。",
))

_reg(IntentPrompt(
    dimension_id=5,
    intent_desc="让论证看起来有凭有据",
    prompt="你说的「研究表明」——是哪项研究？如果你记不起来源，「研究表明」这四个字反而削弱了你的可信度。",
    self_check="不预设用户一定没来源，只问「哪项研究」。",
))

# ── dbs 融合维度（意图层特征）──

_reg(IntentPrompt(
    dimension_id=20,
    intent_desc="让论证无懈可击——堵住所有可能的质疑",
    prompt="你堵的这些反驳，哪个是你真的被人问过的？只留那个。剩下的读者也能感觉到是你想象出来的。",
    self_check="不用「你可能会觉得」开头。不假设用户有反驳。",
))

_reg(IntentPrompt(
    dimension_id=21,
    intent_desc="让概念有记忆点——通过命名来加深印象",
    prompt="你给了两个概念起名字，哪个名字是你真觉得精准的？留那一个。两次以上就变魔术表演了。",
    self_check="不用「本质上」「归根结底」这类被检测词。",
))

_reg(IntentPrompt(
    dimension_id=22,
    intent_desc="在逻辑走到尽头时给出一个答案——用身体感受替代说理",
    prompt="你用「身体知道答案」来收束，是因为你真觉得这件事没法用道理讲清楚，还是因为你讲不下去了？如果讲不下去，直接说讲不下去比编一个身体的答案更真实。",
    self_check="追问本身不用身体隐喻。直接问逻辑链路是否完整。",
))

_reg(IntentPrompt(
    dimension_id=23,
    intent_desc="展示思考深度——把一个实操问题升维到哲学层面",
    prompt="你把一个实操问题升维到了哲学层面。这个话题真的需要升维吗？如果你用到「本质上」「归根结底」，试着删掉那句重新读一遍。",
    self_check="提问本身不升维。不引用抽象概念。",
))

_reg(IntentPrompt(
    dimension_id=24,
    intent_desc="避免重复——同一概念用不同词替换着说",
    prompt="同一段里换了好几个词说同一件事。如果有一个词你觉得最准，重复用。重复不是错。",
    self_check="不用同义词替换的句式。直接说现象。",
))

_reg(IntentPrompt(
    dimension_id=14,
    intent_desc="让读者感觉被尊重、被服务",
    prompt="「让我们共同」「未来可期」——删掉最后一段再读一遍。文章是不是已经结束了？",
    self_check="不评价「谄媚」「套话」。只让用户做比较。",
))

_reg(IntentPrompt(
    dimension_id=15,
    intent_desc="增加画面感和情感冲击",
    prompt="你用了比喻来描述这件事。如果删掉这个比喻，直接用数字或事实说，会不会更有力量？",
    self_check="不攻击比喻的好坏。让用户自己对比。",
))

_reg(IntentPrompt(
    dimension_id=25,
    intent_desc="给文章一个正式的收尾——用「总结」「写在最后」或空洞祝福标记结束",
    prompt="删掉「总结」「写在最后」或结尾的空洞祝福再读一遍。让文章自然停在具体动作、真实场景或留白处，是不是更有余味？读者不需要被提醒「这里要总结了」。",
    self_check="追问直接用可操作的动作（删掉再读），引导自然留白，不评价好坏。",
))

_reg(IntentPrompt(
    dimension_id=18,
    intent_desc="建立清晰的逻辑脉络",
    prompt="搜一下你的全文里有多少个「因此」「所以」「然而」。删掉一半，读者自己能感觉到话锋变了。",
    self_check="不讲大道理。让用户做一个具体操作。",
))

# ── 补齐维度（v1.8.0：追问库从 17/25 补齐到 25/25）──

_reg(IntentPrompt(
    dimension_id=2,
    intent_desc="让结论显得全面、有总结感",
    prompt="「总的来说」「综上所述」这些总结词，删掉再读一遍。结论是不是已经在正文里了？",
    self_check="不评价总结词好坏。只让用户做删掉后的比较。",
))

_reg(IntentPrompt(
    dimension_id=3,
    intent_desc="让读者产生情绪反应",
    prompt="「令人深思」这类词，你想让读者具体感觉到什么？那个感觉换成当时的一个细节是什么？",
    self_check="不攻击情绪词。只问具体细节是什么。",
))

_reg(IntentPrompt(
    dimension_id=9,
    intent_desc="让事情听起来覆盖面广、影响大",
    prompt="「从 X 到 Y」「涵盖多个领域」——实际做的东西是什么？只说那一个。",
    self_check="不预设范围是假的。只问实际做了什么。",
))

_reg(IntentPrompt(
    dimension_id=11,
    intent_desc="跟上平台语感，让同好觉得亲切",
    prompt="这些平台套话里，哪个是你平时真会说的？只留那个，其余换成你自己的说法。",
    self_check="不嘲笑平台语感。只问哪个是真会说的。",
))

_reg(IntentPrompt(
    dimension_id=12,
    intent_desc="让文字读起来顺滑、无磕碰",
    prompt="读一遍你的全文，有没有哪句是你写到一半犹豫过、后来绕了一下才写顺的？把那次绕保留下来。",
    self_check="不用「模板」「流畅」这类词评价。只问犹豫的瞬间。",
))

_reg(IntentPrompt(
    dimension_id=13,
    intent_desc="用格式标记重点，让读者一眼看到",
    prompt="破折号、粗体这些格式，删掉之后哪句还是重点？留那句，其余恢复普通文字。",
    self_check="不评价格式好坏。只问删掉后哪句还是重点。",
))

_reg(IntentPrompt(
    dimension_id=17,
    intent_desc="跟不同读者说话，照顾到各方",
    prompt="这段里「我」「我们」「你」都出现了。你最想站在哪个位置说？只留那一个。",
    self_check="不预设视角错了。只问想站在哪。",
))

_reg(IntentPrompt(
    dimension_id=19,
    intent_desc="让说法有凭有据、可信",
    prompt="这个精确数字是哪来的？是你查到的、算的，还是顺手写的？查不到就改成模糊说法。",
    self_check="不预设数字是假的。只问来源。",
))


def get_prompt(dimension_id: int) -> IntentPrompt | None:
    """获取指定维度的追问提示"""
    return INTENT_PROMPTS.get(dimension_id)
