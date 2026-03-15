from researchclaw.agents.resource_lookup import (
    RankedResourceResult,
    build_resource_query_context,
    format_resource_lookup_response,
    rank_resource_results,
)


def test_build_resource_query_context_detects_exam_request() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    assert context.year == "2025"
    assert "exam_paper" in context.resource_types
    assert "数学" in context.search_query
    assert "pdf" in context.search_query


def test_build_resource_query_context_detects_video_request() -> None:
    context = build_resource_query_context("推荐一下导数教学视频")
    assert context is not None
    assert "video" in context.resource_types
    assert "导数" in context.topic_terms
    assert "数学" in context.search_query


def test_rank_resource_results_prefers_exact_exam_page() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "2025全国各地高考试题及答案出炉！高清PDF版可下载 - 搜狐",
                "url": "https://www.sohu.com/a/902869733_121123754",
                "content": "2025年高考新课标I卷、新课标Ⅱ卷试题及答案，数学试题及答案。",
            },
            {
                "title": "2025年高考数学新课标I卷试题 - 网易",
                "url": "https://www.163.com/dy/article/K1FN4C3K054535JN.html",
                "content": "2025年高考数学新课标I卷试题|广东|山东|数学试卷。",
            },
            {
                "title": "[PDF] 數學 - 香港考試及評核局",
                "url": "https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/math/2025hkdse-c-math.pdf",
                "content": "香港数学 PDF",
            },
        ],
    )
    assert ranked[0].url == "https://www.163.com/dy/article/K1FN4C3K054535JN.html"
    assert ranked[-1].source_host == "www.hkeaa.edu.hk"


def test_format_resource_lookup_response_contains_links() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "2025年高考数学新课标I卷试题 - 网易",
                "url": "https://www.163.com/dy/article/K1FN4C3K054535JN.html",
                "content": "2025年高考数学新课标I卷试题|广东|山东|数学试卷。",
            },
        ],
    )
    response = format_resource_lookup_response(
        context,
        ranked,
        excerpt="提取内容明确包含新课标I卷数学试题。",
        verified_title="2025年高考数学新课标I卷试题|广东|山东|数学试卷_网易订阅",
    )
    assert "链接：https://www.163.com/dy/article/K1FN4C3K054535JN.html" in response
    assert "已验证页面标题" in response


def test_rank_resource_results_dedupes_canonical_url_variants() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "北京市2025年高考数学试卷 - 中国教育在线",
                "url": "https://gaokao.eol.cn/2025/20250607/20250607161113.html",
                "content": "北京市2025年高考数学试卷。",
            },
            {
                "title": "北京市2025年高考数学试卷 - 中国教育在线",
                "url": "https://gaokao.eol.cn/2025/20250607/20250607161113.html?from=tavily",
                "content": "北京市2025年高考数学试卷。",
            },
            {
                "title": "北京市2025年高考数学试卷 - 中国教育在线",
                "url": "https://gaokao.eol.cn/2025/20250607/20250607161113.html#section",
                "content": "北京市2025年高考数学试卷。",
            },
        ],
    )
    assert len(ranked) == 1
    assert ranked[0].url == "https://gaokao.eol.cn/2025/20250607/20250607161113.html"


def test_format_resource_lookup_response_diversifies_hosts() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    results = [
        RankedResourceResult(
            title="A",
            url="https://gaokao.eol.cn/a.html",
            snippet="a",
            score=100,
            source_host="gaokao.eol.cn",
            matched_terms=("2025",),
        ),
        RankedResourceResult(
            title="B",
            url="https://gaokao.eol.cn/b.html",
            snippet="b",
            score=99,
            source_host="gaokao.eol.cn",
            matched_terms=("2025",),
        ),
        RankedResourceResult(
            title="C",
            url="https://www.163.com/c.html",
            snippet="c",
            score=98,
            source_host="www.163.com",
            matched_terms=("2025",),
        ),
        RankedResourceResult(
            title="D",
            url="https://www.sohu.com/d.html",
            snippet="d",
            score=97,
            source_host="www.sohu.com",
            matched_terms=("2025",),
        ),
    ]
    response = format_resource_lookup_response(context, results)
    assert "链接：https://gaokao.eol.cn/a.html" in response
    assert "链接：https://www.163.com/c.html" in response
    assert "链接：https://www.sohu.com/d.html" in response
    assert "链接：https://gaokao.eol.cn/b.html" not in response


def test_build_resource_query_context_defaults_exam_requests_to_math() -> None:
    context = build_resource_query_context("帮我找北京市2025年的一些影响力非常大的试卷")
    assert context is not None
    assert context.search_query.endswith("数学 试卷 pdf") or "数学" in context.search_query


def test_rank_resource_results_boosts_query_location_matches() -> None:
    context = build_resource_query_context("帮我找北京市2025年的一些影响力非常大的试卷")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "2025年高考综合改革适应性测试数学试卷 - 河南升学网",
                "url": "http://www.hnzsks.com.cn/index/index/articledetail/id/10437.html",
                "content": "2025年高考综合改革适应性测试数学试卷评析。",
            },
            {
                "title": "2025 普通高等学校招生全国统一考试（北京卷） 数学",
                "url": "https://cdn.gaokzx.com/zixunzhan/17497087416252025%E5%8C%97%E4%BA%AC%E9%AB%98%E8%80%83%E6%95%B0%E5%AD%A6%E8%AF%95%E9%A2%98.pdf",
                "content": "2025 北京高考数学试题 pdf",
            },
            {
                "title": "北京市2025年高考数学试卷 - 中国教育在线",
                "url": "https://gaokao.eol.cn/2025/20250607/20250607161113.html",
                "content": "北京市2025年高考数学试卷。",
            },
        ],
    )
    assert ranked[0].url in {
        "https://cdn.gaokzx.com/zixunzhan/17497087416252025%E5%8C%97%E4%BA%AC%E9%AB%98%E8%80%83%E6%95%B0%E5%AD%A6%E8%AF%95%E9%A2%98.pdf",
        "https://gaokao.eol.cn/2025/20250607/20250607161113.html",
    }
    assert ranked[1].url in {
        "https://cdn.gaokzx.com/zixunzhan/17497087416252025%E5%8C%97%E4%BA%AC%E9%AB%98%E8%80%83%E6%95%B0%E5%AD%A6%E8%AF%95%E9%A2%98.pdf",
        "https://gaokao.eol.cn/2025/20250607/20250607161113.html",
    }
    assert ranked[-1].url == "http://www.hnzsks.com.cn/index/index/articledetail/id/10437.html"
