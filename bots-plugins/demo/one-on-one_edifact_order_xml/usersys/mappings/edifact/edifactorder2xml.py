# mapping-script
from bots import transform


def tag2validxmltag(node):
    """
    edifact tags are numerical;
    xml does not allow numerical tags.
    This function fixed this
    """
    if node.record is not None:
        for key in list(node.record.keys()):
            if key not in ["BOTSID", "BOTSIDnr"]:
                # character '#' is not allowed in xml
                node.record["_" + key.replace("#", "_")] = node.record.pop(key)

    for child in node.children:
        tag2validxmltag(child)


def main(inn, out):
    transform.inn2out(inn, out)
    # edifact tags are numerical; xml does not allow numerical tags. This function fixed this
    tag2validxmltag(out.root)
