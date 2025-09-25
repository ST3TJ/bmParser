class Mode:
    def __init__(
        self,
        mask: int = 0b1,
        *,
        ignore_padding: bool = False,
        only_padding: bool = False,
    ):
        self.mask = mask
        self.ignore_padding = ignore_padding
        self.only_padding = only_padding
        if only_padding:
            self.ignore_padding = False

    def __str__(self) -> str:
        return f"Mode(mask=0b{self.mask:b}, ignore_padding={self.ignore_padding}, only_padding={self.only_padding})"

    def __repr__(self) -> str:
        return f"<Mode mask=0b{self.mask:b} ignore_padding={self.ignore_padding} only_padding={self.only_padding}>"
