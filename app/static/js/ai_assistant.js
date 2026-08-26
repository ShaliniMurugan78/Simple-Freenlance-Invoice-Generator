/**
 * AI Invoice Description Assistant Client Handler
 */

document.addEventListener("DOMContentLoaded", () => {
  const generateBtn = document.getElementById("aiGenerateBtn");
  const serviceInput = document.getElementById("aiServiceName");
  const contextInput = document.getElementById("aiContext");
  const toneSelect = document.getElementById("aiTone");
  const resultBox = document.getElementById("aiResultBox");
  const descOutput = document.getElementById("aiGeneratedText");
  const applyBtn = document.getElementById("aiApplyBtn");
  const statusMsg = document.getElementById("aiStatusMsg");

  if (!generateBtn) return;

  generateBtn.addEventListener("click", async () => {
    const serviceName = serviceInput.value.trim();
    if (!serviceName) {
      alert("Please enter a service name (e.g. Website Development, UI/UX Design).");
      serviceInput.focus();
      return;
    }

    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";
    statusMsg.textContent = "Synthesizing description...";
    resultBox.style.display = "none";

    try {
      const resp = await fetch("/api/ai/generate-description", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: serviceName,
          context: contextInput ? contextInput.value.trim() : "",
          tone: toneSelect ? toneSelect.value : "Professional"
        })
      });

      const data = await resp.json();
      if (data.success && data.description) {
        descOutput.textContent = data.description;
        resultBox.style.display = "block";
        statusMsg.textContent = data.message || "Generated successfully.";
      } else {
        alert(data.message || "Unable to generate description.");
        statusMsg.textContent = "Generation failed.";
      }
    } catch (err) {
      console.error("AI Error:", err);
      alert("Error connecting to AI service.");
      statusMsg.textContent = "Network error.";
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate Description";
    }
  });

  if (applyBtn) {
    applyBtn.addEventListener("click", () => {
      const text = descOutput.textContent.trim();
      if (text && window.activeRowForAI) {
        const descField = window.activeRowForAI.querySelector(".item-description");
        if (descField) {
          descField.value = text;
        }
        // Close modal
        const aiModal = document.getElementById("aiModal");
        if (aiModal) aiModal.classList.remove("active");
      }
    });
  }
});
