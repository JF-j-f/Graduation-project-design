// 设置页面 JavaScript 交互功能

document.addEventListener('DOMContentLoaded', function() {
    initializeSettingsPage();
});

/**
 * 初始化设置页面
 */
function initializeSettingsPage() {
    setupTabNavigation();
    setupFormValidation();
    setupPasswordStrengthCheck();
    setupDeleteAccountModal();
    setupLoadingOverlay();
}

/**
 * 设置标签页导航
 */
function setupTabNavigation() {
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    const tabContents = document.querySelectorAll('.tab-content');

    sidebarItems.forEach(item => {
        item.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');

            // 移除所有活动状态
            sidebarItems.forEach(si => si.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));

            // 添加当前活动状态
            this.classList.add('active');
            document.getElementById(targetTab + '-tab').classList.add('active');
        });
    });
}

/**
 * 设置表单验证
 */
function setupFormValidation() {
    // 个人信息表单验证
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            if (!validateProfileForm()) {
                e.preventDefault();
                return false;
            }
            showLoading();
        });
    }

    // 密码修改表单验证
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', function(e) {
            if (!validatePasswordForm()) {
                e.preventDefault();
                return false;
            }
            showLoading();
        });
    }

    // 实时输入验证
    setupRealTimeValidation();
}

/**
 * 设置实时验证
 */
function setupRealTimeValidation() {
    // 邮箱验证
    const emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            validateEmail(this);
        });
    }

    // 手机号验证
    const phoneInput = document.getElementById('phone');
    if (phoneInput) {
        phoneInput.addEventListener('blur', function() {
            validatePhone(this);
        });
    }

    // 昵称验证
    const nicknameInput = document.getElementById('nickname');
    if (nicknameInput) {
        nicknameInput.addEventListener('blur', function() {
            validateNickname(this);
        });
    }
}

/**
 * 验证个人信息表单
 */
function validateProfileForm() {
    let isValid = true;
    let errorMessage = '';

    // 验证昵称
    const nickname = document.getElementById('nickname');
    if (!validateNickname(nickname)) {
        isValid = false;
        errorMessage += '请检查昵称格式。';
    }

    // 验证邮箱
    const email = document.getElementById('email');
    if (!validateEmail(email)) {
        isValid = false;
        errorMessage += '请检查邮箱格式。';
    }

    // 验证手机号
    const phone = document.getElementById('phone');
    if (!validatePhone(phone)) {
        isValid = false;
        errorMessage += '请检查手机号格式。';
    }

    if (!isValid) {
        showError('表单验证失败：' + errorMessage);
    }

    return isValid;
}

/**
 * 验证昵称
 */
function validateNickname(input) {
    if (!input) return true;

    const value = input.value.trim();
    const formGroup = input.closest('.form-group');

    // 移除之前的错误提示
    removeError(formGroup);

    if (value && value.length > 50) {
        showErrorOnField(formGroup, '昵称长度不能超过50个字符');
        return false;
    }

    if (value && (value.includes('<script>') || value.includes('javascript:'))) {
        showErrorOnField(formGroup, '昵称包含非法字符');
        return false;
    }

    return true;
}

/**
 * 验证邮箱
 */
function validateEmail(input) {
    if (!input) return true;

    const value = input.value.trim();
    const formGroup = input.closest('.form-group');

    // 移除之前的错误提示
    removeError(formGroup);

    if (value && !isValidEmailFormat(value)) {
        showErrorOnField(formGroup, '请输入有效的邮箱地址');
        return false;
    }

    if (value && value.length > 100) {
        showErrorOnField(formGroup, '邮箱地址过长');
        return false;
    }

    return true;
}

/**
 * 验证手机号
 */
function validatePhone(input) {
    if (!input) return true;

    const value = input.value.trim();
    const formGroup = input.closest('.form-group');

    // 移除之前的错误提示
    removeError(formGroup);

    if (value && !isValidPhoneFormat(value)) {
        showErrorOnField(formGroup, '请输入有效的手机号码');
        return false;
    }

    return true;
}

/**
 * 验证密码表单
 */
function validatePasswordForm() {
    let isValid = true;
    let errorMessage = '';

    const currentPassword = document.getElementById('currentPassword');
    const newPassword = document.getElementById('newPassword');
    const confirmPassword = document.getElementById('confirmPassword');

    // 验证当前密码
    if (!currentPassword.value.trim()) {
        isValid = false;
        errorMessage += '请输入当前密码。';
    }

    // 验证新密码
    if (!newPassword.value.trim()) {
        isValid = false;
        errorMessage += '请输入新密码。';
    } else if (newPassword.value.length < 6) {
        isValid = false;
        errorMessage += '新密码长度不能少于6位。';
    } else if (newPassword.value.length > 20) {
        isValid = false;
        errorMessage += '新密码长度不能超过20位。';
    } else if (!isPasswordStrong(newPassword.value)) {
        isValid = false;
        errorMessage += '新密码强度较弱，请包含字母、数字或特殊字符。';
    }

    // 验证新密码不能与当前密码相同
    if (currentPassword.value && newPassword.value && currentPassword.value === newPassword.value) {
        isValid = false;
        errorMessage += '新密码不能与当前密码相同。';
    }

    // 验证确认密码
    if (!confirmPassword.value.trim()) {
        isValid = false;
        errorMessage += '请确认新密码。';
    } else if (newPassword.value !== confirmPassword.value) {
        isValid = false;
        errorMessage += '两次输入的密码不一致。';
    }

    if (!isValid) {
        showError('表单验证失败：' + errorMessage);
    }

    return isValid;
}

/**
 * 设置密码强度检测
 */
function setupPasswordStrengthCheck() {
    const newPasswordInput = document.getElementById('newPassword');
    if (newPasswordInput) {
        newPasswordInput.addEventListener('input', function() {
            checkPasswordStrength(this.value);
        });
    }
}

/**
 * 检查密码强度
 */
function checkPasswordStrength(password) {
    const strengthFill = document.querySelector('.strength-fill');
    const strengthText = document.querySelector('.strength-text');

    if (!strengthFill || !strengthText) return;

    let strength = 0;

    // 长度检查
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;

    // 字符类型检查
    if (/[a-z]/.test(password)) strength++; // 小写字母
    if (/[A-Z]/.test(password)) strength++; // 大写字母
    if (/[0-9]/.test(password)) strength++; // 数字
    if (/[^a-zA-Z0-9]/.test(password)) strength++; // 特殊字符

    // 更新显示
    if (strength <= 2) {
        strengthFill.className = 'strength-fill weak';
        strengthText.textContent = '密码强度：弱';
        strengthText.style.color = '#dc3545';
    } else if (strength <= 4) {
        strengthFill.className = 'strength-fill medium';
        strengthText.textContent = '密码强度：中等';
        strengthText.style.color = '#ffc107';
    } else {
        strengthFill.className = 'strength-fill strong';
        strengthText.textContent = '密码强度：强';
        strengthText.style.color = '#28a745';
    }
}

/**
 * 设置注销账户模态框
 */
function setupDeleteAccountModal() {
    const confirmCheckbox = document.getElementById('confirmDeleteCheckbox');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const deletePasswordInput = document.getElementById('deletePasswordConfirm');

    // 复选框状态监听
    if (confirmCheckbox && confirmDeleteBtn) {
        confirmCheckbox.addEventListener('change', function() {
            confirmDeleteBtn.disabled = !this.checked;
        });
    }

    // 密码输入监听
    if (deletePasswordInput) {
        deletePasswordInput.addEventListener('input', function() {
            const passwordError = document.getElementById('passwordError');
            if (passwordError) {
                passwordError.textContent = '';
            }
        });
    }

    // 模态框外部点击关闭
    const modal = document.getElementById('deleteAccountModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeDeleteAccountModal();
            }
        });
    }

    // ESC 键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDeleteAccountModal();
        }
    });
}

/**
 * 显示注销账户模态框
 */
function showDeleteAccountModal() {
    const modal = document.getElementById('deleteAccountModal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';

        // 重置表单状态
        setTimeout(() => {
            document.getElementById('confirmDeleteCheckbox').checked = false;
            document.getElementById('confirmDeleteBtn').disabled = true;
            document.getElementById('deletePasswordConfirm').value = '';
            document.getElementById('passwordError').textContent = '';
        }, 100);
    }
}

/**
 * 关闭注销账户模态框
 */
function closeDeleteAccountModal() {
    const modal = document.getElementById('deleteAccountModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

/**
 * 确认注销账户
 */
function confirmDeleteAccount() {
    const password = document.getElementById('deletePasswordConfirm').value;
    const passwordError = document.getElementById('passwordError');

    if (!password || password.trim() === '') {
        passwordError.textContent = '请输入密码确认操作';
        return;
    }

    // 创建表单并提交
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = 'deleteAccount';

    const passwordInput = document.createElement('input');
    passwordInput.type = 'hidden';
    passwordInput.name = 'passwordConfirm';
    passwordInput.value = password;

    form.appendChild(passwordInput);
    document.body.appendChild(form);

    showLoading();
    form.submit();
}

/**
 * 设置加载遮罩
 */
function setupLoadingOverlay() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        // 点击遮罩不关闭
        loadingOverlay.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
}

/**
 * 显示加载遮罩
 */
function showLoading() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('show');
    }
}

/**
 * 隐藏加载遮罩
 */
function hideLoading() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('show');
    }
}

/**
 * 重置表单
 */
function resetForm() {
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.reset();
        // 移除所有错误提示
        document.querySelectorAll('.error-message').forEach(error => {
            error.remove();
        });
    }
}

/**
 * 显示错误消息
 */
function showError(message) {
    // 创建临时提示
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-error alert-temporary';
    errorDiv.innerHTML = `
        <span class="alert-icon">❌</span>
        <span>${message}</span>
    `;

    // 插入到页面顶部
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(errorDiv, mainContainer.firstChild);

        // 3秒后自动移除
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 3000);
    }
}

/**
 * 在表单字段上显示错误
 */
function showErrorOnField(formGroup, message) {
    removeError(formGroup);

    const errorElement = document.createElement('span');
    errorElement.className = 'error-message';
    errorElement.textContent = message;
    errorElement.style.color = '#dc3545';
    errorElement.style.fontSize = '0.85rem';
    errorElement.style.marginTop = '0.25rem';
    errorElement.style.display = 'block';

    formGroup.appendChild(errorElement);

    // 高亮输入框
    const input = formGroup.querySelector('.form-input');
    if (input) {
        input.style.borderColor = '#dc3545';
        input.style.boxShadow = '0 0 0 3px rgba(220, 53, 69, 0.1)';
    }
}

/**
 * 移除表单字段错误
 */
function removeError(formGroup) {
    const errorElement = formGroup.querySelector('.error-message');
    if (errorElement) {
        errorElement.remove();
    }

    const input = formGroup.querySelector('.form-input');
    if (input) {
        input.style.borderColor = '';
        input.style.boxShadow = '';
    }
}

/**
 * 邮箱格式验证
 */
function isValidEmailFormat(email) {
    const emailRegex = /^[a-zA-Z0-9_+&*-]+(?:\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,7}$/;
    return emailRegex.test(email);
}

/**
 * 手机号格式验证
 */
function isValidPhoneFormat(phone) {
    const phoneRegex = /^1[3-9]\d{9}$/;
    return phoneRegex.test(phone);
}

/**
 * 密码强度检查
 */
function isPasswordStrong(password) {
    let hasLetter = false;
    let hasDigit = false;
    let hasSpecial = false;

    for (let c of password) {
        if (/[a-zA-Z]/.test(c)) hasLetter = true;
        else if (/[0-9]/.test(c)) hasDigit = true;
        else hasSpecial = true;
    }

    // 至少包含两种字符类型
    return (hasLetter && hasDigit) || (hasLetter && hasSpecial) || (hasDigit && hasSpecial);
}

/**
 * 页面加载完成后隐藏加载遮罩
 */
window.addEventListener('load', function() {
    hideLoading();
});

/**
 * 处理浏览器后退按钮
 */
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        hideLoading();
    }
});