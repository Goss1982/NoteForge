from .schemas import DocumentContent


def markdown(content: DocumentContent, page_numbers: dict[str, int], *, reviewed: bool, revision_id: str):
    lines = [
        f"# {content.title}",
        "",
        "Reviewed by user" if reviewed else "DRAFT — unverified AI output; review against original notes.",
        f"Source revision: {revision_id}",
        "",
    ]
    for section in content.sections:
        lines += [f"## {section.heading}", ""]
        for p in section.paragraphs:
            lines += [f"**{p.kind.title()}** — {p.text}", ""]
            for c in p.citations:
                lines += [f"> Source page {page_numbers[c.page_id]} ({c.page_id}): {c.quote}", ""]
    if content.missing_information:
        lines += ["## Missing information", "", *[f"- {s}" for s in content.missing_information], ""]
    return "\n".join(lines)
