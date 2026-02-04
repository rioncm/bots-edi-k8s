# mapping-script
from bots import transform


def xmltag2edifacttag(node):
    """
    edifact tags are numerical;
    xml does not allow numerical tags.
    This function fixed this
    Convert xml tag > edifact tag
    _EDI > EDI
    """
    if node.record is not None:
        for key in list(node.record.keys()):
            if key not in ["BOTSID", "BOTSIDnr"]:
                node.record[key[1:].replace("_", "#")] = node.record.pop(key)

    for child in node.children:
        xmltag2edifacttag(child)


def main(inn, out):
    out.ta_info["frompartner"] = "FAKE FROM PARTNER"  # only a demo
    out.ta_info["topartner"] = "FAKE TO PARTNER"  # only a demo
    transform.inn2out(inn, out)
    # edifact tags are numerical; xml does not allow numerical tags. This function fixed this
    xmltag2edifacttag(out.root)
