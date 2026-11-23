"""Compatibility discovery for the official data pack and connected libraries."""


def library(kind=None, workspace=None):
    from nbt_assets.libraries import recipes
    return recipes(workspace, kind)
