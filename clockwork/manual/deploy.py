from pyinfra.operations import apt

apt.packages(
    name="Install vim",
    packages=["vim"],
    update=True,
)
