class TokenMeter < Formula
  desc "Local coding-agent usage dashboard and menu bar companion"
  homepage "https://github.com/splunk/token-meter"
  license "MIT"
  head "https://github.com/splunk/token-meter.git", branch: "main"

  depends_on :macos
  depends_on "python@3.14"

  def install
    libexec.install %w[meter.py page.html performance.html token_meter_mcp.py
                      runtime-manifest.txt token_meter menubar scripts assets README.md LICENSE]
    libexec.install "RELEASE_VERSION" if File.exist?("RELEASE_VERSION")
    (libexec/"RELEASE_VERSION").write "#{version}\n" unless (libexec/"RELEASE_VERSION").exist?
    (bin/"token-meter").write <<~SH
      #!/bin/bash
      export PATH="#{Formula["python@3.14"].opt_bin}:$PATH"
      exec "#{opt_libexec}/scripts/package-homebrew" "$@"
    SH
  end

  def caveats
    <<~EOS
      Activate the per-user server and menu bar companion:
        token-meter install
      Or install the server alone:
        token-meter install --backend-only
      Updates are owned by Homebrew:
        brew upgrade token-meter
        token-meter install
      Re-run activation after each upgrade to restart the per-user runtime.
      Stop automatic startup before removing the formula:
        token-meter uninstall
        brew uninstall token-meter
      Dashboard: http://127.0.0.1:8722
    EOS
  end

  test do
    ENV["PYTHONPYCACHEPREFIX"] = (testpath/"pycache").to_s
    assert_match "token-meter install", shell_output("#{bin}/token-meter --help")
    system Formula["python@3.14"].opt_bin/"python3.14", "-m", "py_compile", libexec/"meter.py"
    cd libexec do
      system Formula["python@3.14"].opt_bin/"python3.14", "-m", "token_meter.packaging",
             "manifest", libexec/"runtime-manifest.txt"
    end
  end
end
