class TriformCli < Formula
  desc "CLI tool to sync and execute Triform projects"
  homepage "https://triform.ai"
  url "https://files.pythonhosted.org/packages/source/t/triform-cli/triform_cli-0.1.0.tar.gz"
  sha256 "c528521a0b96b4b059fa7f63f1336ff0320291c266a84821edf1e943864b2853"
  license "MIT"

  depends_on "python@3.12"

  def install
    python3 = "python3.12"
    system python3, "-m", "pip", "install", *std_pip_args, "."
  end

  test do
    system bin/"triform", "--help"
  end
end

